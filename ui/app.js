/**
 * TradePulse Desktop Client Application — Elite Edition
 * Institutional Real Market & Quotex OTC Signal Station
 */

// Global Application State
const AppState = {
  connected: false,
  running: true,
  toolActive: true,
  soundEnabled: true,
  prices: {},
  previousPrices: {},
  priceDirections: {},
  priceSources: {},
  payouts: {},
  watchedMarkets: {},
  favorites: new Set(),
  allAssets: [],
  marketCategory: 'ALL',
  marketSearchQuery: '',
  strategies: [],
  signals: [],
  stats: { total: 0, win_rate: 0, wins: 0, losses: 0, draws: 0 },
  activeView: 'monitor',
  selectedStrategyId: null,
  selectedStrategyAssets: new Set(),
  activeAssetScope: 'ALL_MARKETS',
  selectedMarket: null,
  activeDirection: 'CALL',
  activeTimeframe: '1M',
  historyFilter: 'ALL',
  historySearchQuery: '',
  voiceEnabled: true,
  preAlertsEnabled: true,
  otcFlatlineGuardEnabled: true,
  confluenceScannerEnabled: true,
  preSignals: [],
  terminalLayout: 'monitor',
  marketViewMode: 'table',
  marketPayoutFilter: 0,
  advancedFilters: null,
  riskMetrics: null,
  upcomingNews: []
};

// Web Audio API Chime Synthesizer
const SoundEngine = {
  ctx: null,
  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) this.ctx = new AudioContext();
    }
  },
  playChime(isCall = true) {
    if (!AppState.soundEnabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      if (this.ctx.state === 'suspended') this.ctx.resume();

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);

      const now = this.ctx.currentTime;
      if (isCall) {
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.exponentialRampToValueAtTime(783.99, now + 0.12); // G5
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.linearRampToValueAtTime(0.01, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      } else {
        osc.frequency.setValueAtTime(659.25, now); // E5
        osc.frequency.exponentialRampToValueAtTime(392.00, now + 0.14); // G4
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.linearRampToValueAtTime(0.01, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      }
    } catch (e) {
      console.warn('[AUDIO] Failed to play chime:', e);
    }
  },
  mute() {
    if (this.ctx && this.ctx.state === 'running') {
      try { this.ctx.suspend(); } catch(e) {}
    }
  },
  unmute() {
    if (this.ctx && this.ctx.state === 'suspended') {
      try { this.ctx.resume(); } catch(e) {}
    }
  }
};

// Web Speech API Voice Synthesizer
const VoiceEngine = {
  speak(text) {
    if (!AppState.soundEnabled || !AppState.voiceEnabled) return;
    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      const voices = window.speechSynthesis.getVoices();
      const engVoice = voices.find(v => v.lang && v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('David') || v.name.includes('Zira')));
      if (engVoice) utterance.voice = engVoice;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('[VOICE] Speech error:', e);
    }
  },
  announceSignal(sig) {
    if (!AppState.soundEnabled || !AppState.voiceEnabled) return;
    const cleanSym = (sig.asset_symbol || '').replace(' (OTC)', ' OTC').replace('_otc', ' OTC').replace('/', ' ');
    const dir = (sig.direction || '').toUpperCase() === 'CALL' ? 'Call' : 'Put';
    const duration = sig.duration_minutes ? `${sig.duration_minutes} minute` : '';
    this.speak(`Trade alert: ${dir} on ${cleanSym}. Expiry ${duration}.`);
  },
  announcePreSignal(pre) {
    if (!AppState.soundEnabled || !AppState.voiceEnabled) return;
    const cleanSym = (pre.symbol || '').replace(' (OTC)', ' OTC').replace('_otc', ' OTC').replace('/', ' ');
    const dir = (pre.direction || '').toUpperCase() === 'CALL' ? 'Call' : 'Put';
    const sec = pre.remaining_seconds || 15;
    this.speak(`Get ready: ${dir} on ${cleanSym} in ${sec} seconds.`);
  },
  stop() {
    if ('speechSynthesis' in window) {
      try { window.speechSynthesis.cancel(); } catch(e) {}
    }
  }
};

// UI Notification and Utility Helpers
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) toast.remove();
  }, 3000);
}
window.showToast = showToast;

// ============================================================================
// Initialization & Live Market Clock
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  // Load local favorites
  const savedFavs = localStorage.getItem('tradepulse_favorites');
  if (savedFavs) {
    try {
      const parsed = JSON.parse(savedFavs);
      if (Array.isArray(parsed)) AppState.favorites = new Set(parsed);
    } catch(e) {}
  }

  // Load local preferences
  const savedWatched = localStorage.getItem('tradepulse_watched_markets');
  if (savedWatched) {
    try { AppState.watchedMarkets = JSON.parse(savedWatched); } catch(e){}
  }
  const savedSound = localStorage.getItem('tradepulse_sound_pref');
  if (savedSound !== null) {
    AppState.soundEnabled = (savedSound === 'true');
  }
  updateSoundUI(AppState.soundEnabled);
  if (!AppState.soundEnabled) {
    VoiceEngine.stop();
    SoundEngine.mute();
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_app_muted) {
      window.pywebview.api.set_app_muted(true);
    }
  }
  const savedVoice = localStorage.getItem('tradepulse_voice_enabled');
  if (savedVoice !== null) AppState.voiceEnabled = savedVoice === 'true';
  const voiceToggle = document.getElementById('pref-voice-toggle');
  if (voiceToggle) voiceToggle.checked = AppState.voiceEnabled;

  const savedPreAlerts = localStorage.getItem('tradepulse_pre_alerts');
  if (savedPreAlerts !== null) AppState.preAlertsEnabled = savedPreAlerts === 'true';
  const preToggle = document.getElementById('pref-presignal-toggle');
  if (preToggle) preToggle.checked = AppState.preAlertsEnabled;

  const savedFlatline = localStorage.getItem('tradepulse_otc_flatline_guard');
  if (savedFlatline !== null) AppState.otcFlatlineGuardEnabled = savedFlatline === 'true';
  const flatToggle = document.getElementById('pref-flatline-toggle');
  if (flatToggle) flatToggle.checked = AppState.otcFlatlineGuardEnabled;

  const savedConfluence = localStorage.getItem('tradepulse_confluence_scanner');
  if (savedConfluence !== null) AppState.confluenceScannerEnabled = savedConfluence === 'true';
  const confToggle = document.getElementById('pref-confluence-toggle');
  if (confToggle) confToggle.checked = AppState.confluenceScannerEnabled;

  const savedCooldown = localStorage.getItem('tradepulse_cooldown_pref');
  if (savedCooldown) {
    const cdInput = document.getElementById('pref-cooldown');
    if (cdInput) cdInput.value = savedCooldown;
  }

  // Start live clock
  startLiveClock();

  // Start countdown ticker for signal cards
  setInterval(updateActiveCountdowns, 1000);

  // Hook PyWebView API
  window.addEventListener('pywebviewready', () => {
    console.log('[UI] PyWebView API Ready.');
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.get_initial_state().then(initFullState);
      if (savedCooldown && window.pywebview.api.set_global_cooldown) {
        window.pywebview.api.set_global_cooldown(parseInt(savedCooldown, 10));
      }
      if (window.pywebview.api.get_feature_toggles) {
        window.pywebview.api.get_feature_toggles().then(toggles => {
          if (toggles) {
            if (toggles.otc_flatline_guard !== undefined) {
              AppState.otcFlatlineGuardEnabled = toggles.otc_flatline_guard;
              if (flatToggle) flatToggle.checked = toggles.otc_flatline_guard;
            }
            if (toggles.pre_alerts !== undefined) {
              AppState.preAlertsEnabled = toggles.pre_alerts;
              if (preToggle) preToggle.checked = toggles.pre_alerts;
            }
            if (toggles.voice_alerts !== undefined) {
              AppState.voiceEnabled = toggles.voice_alerts;
              if (voiceToggle) voiceToggle.checked = toggles.voice_alerts;
            }
            if (toggles.confluence_scanner !== undefined) {
              AppState.confluenceScannerEnabled = toggles.confluence_scanner;
              if (confToggle) confToggle.checked = toggles.confluence_scanner;
            }
          }
        }).catch(e => console.debug('[TOGGLES] Load note:', e));
      }
      loadStrategyLeaderboard();
    }
  });
});

function startLiveClock() {
  function tick() {
    const now = new Date();
    const utcEl = document.getElementById('live-utc-clock');
    const localEl = document.getElementById('live-local-clock');
    if (utcEl) {
      const uH = String(now.getUTCHours()).padStart(2, '0');
      const uM = String(now.getUTCMinutes()).padStart(2, '0');
      const uS = String(now.getUTCSeconds()).padStart(2, '0');
      utcEl.textContent = `${uH}:${uM}:${uS}`;
    }
    if (localEl) {
      const lH = String(now.getHours()).padStart(2, '0');
      const lM = String(now.getMinutes()).padStart(2, '0');
      localEl.textContent = `${lH}:${lM}`;
    }
  }
  tick();
  setInterval(tick, 1000);
}

function toggleQuickSound() {
  AppState.soundEnabled = !AppState.soundEnabled;
  localStorage.setItem('tradepulse_sound_pref', AppState.soundEnabled ? 'true' : 'false');
  updateSoundUI(AppState.soundEnabled);

  if (AppState.soundEnabled) {
    SoundEngine.unmute();
    SoundEngine.playChime(true);
    showToast('Sound & Voice Alerts: ACTIVE', 'success');
  } else {
    SoundEngine.mute();
    VoiceEngine.stop();
    showToast('Sound & Voice Alerts: MUTED', 'info');
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_app_muted) {
    window.pywebview.api.set_app_muted(!AppState.soundEnabled);
  }
}
window.toggleQuickSound = toggleQuickSound;

function toggleSoundPref(checkbox) {
  AppState.soundEnabled = checkbox.checked;
  localStorage.setItem('tradepulse_sound_pref', AppState.soundEnabled ? 'true' : 'false');
  updateSoundUI(AppState.soundEnabled);

  if (AppState.soundEnabled) {
    SoundEngine.unmute();
    SoundEngine.playChime(true);
  } else {
    SoundEngine.mute();
    VoiceEngine.stop();
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_app_muted) {
    window.pywebview.api.set_app_muted(!AppState.soundEnabled);
  }
}
window.toggleSoundPref = toggleSoundPref;

function updateSoundUI(enabled) {
  const quickBtn = document.getElementById('quick-sound-btn');
  const quickIcon = document.getElementById('quick-sound-icon');
  const quickText = document.getElementById('quick-sound-text');
  const prefToggle = document.getElementById('pref-sound-toggle');

  if (quickBtn) {
    if (enabled) {
      quickBtn.className = 'btn-sound-pill active';
      if (quickIcon) quickIcon.textContent = '🔔';
      if (quickText) quickText.textContent = 'Audio ON';
      quickBtn.title = 'Sound is ON. Click to Mute all alerts and broker audio';
    } else {
      quickBtn.className = 'btn-sound-pill muted';
      if (quickIcon) quickIcon.textContent = '🔕';
      if (quickText) quickText.textContent = 'Muted';
      quickBtn.title = 'Sound is MUTED. Click to Unmute alerts and broker audio';
    }
  }
  if (prefToggle) {
    prefToggle.checked = enabled;
  }
}

function toggleFavorite(symbol, event) {
  if (event) event.stopPropagation();
  if (AppState.favorites.has(symbol)) {
    AppState.favorites.delete(symbol);
  } else {
    AppState.favorites.add(symbol);
  }
  localStorage.setItem('tradepulse_favorites', JSON.stringify(Array.from(AppState.favorites)));

  // If viewing Favorites tab, re-render
  if (AppState.marketCategory === 'FAVORITES') {
    renderMarketsTable();
  } else {
    // Update individual row star icon
    const row = document.getElementById(`row-${sanitizeId(symbol)}`);
    if (row) {
      const btn = row.querySelector('.btn-star-fav');
      if (btn) {
        const isFav = AppState.favorites.has(symbol);
        btn.className = `btn-star-fav ${isFav ? 'is-favorite' : ''}`;
        btn.textContent = isFav ? '★' : '☆';
      }
    }
  }
}
window.toggleFavorite = toggleFavorite;

// ============================================================================
// Core Navigation & View Switching
// ============================================================================
function switchView(viewId) {
  AppState.activeView = viewId;

  // Update nav items
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${viewId}`);
  if (activeNav) activeNav.classList.add('active');

  // Update view panes
  document.querySelectorAll('.view-pane').forEach(el => el.classList.remove('active'));
  const activePane = document.getElementById(`view-${viewId}`);
  if (activePane) activePane.classList.add('active');

  // Specific view refresh handlers
  if (viewId === 'chart') {
    if (window.initLiveChartStation) {
      window.initLiveChartStation();
    }
  } else if (viewId === 'strategies') {
    if (!AppState.selectedStrategyId && AppState.strategies.length > 0) {
      selectStrategy(AppState.strategies[0].id);
    } else {
      renderStrategyList();
      if (AppState.selectedStrategyId) {
        selectStrategy(AppState.selectedStrategyId);
      }
    }
  } else if (viewId === 'history') {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_signals_history) {
      window.pywebview.api.get_signals_history(100).then(sigs => {
        if (Array.isArray(sigs)) {
          AppState.signals = sigs;
        }
        renderHistoryTable();
      }).catch(() => renderHistoryTable());
    } else {
      renderHistoryTable();
    }
  } else if (viewId === 'telegram') {
    if (window.renderTelegramManager) {
      window.renderTelegramManager();
    }
  }

  // Synchronize embedded native broker visibility
  if (window.pywebview && window.pywebview.api) {
    syncBrokerStationLayout(true);
    setTimeout(() => syncBrokerStationLayout(true), 60);
  }
}
window.switchView = switchView;

function switchTerminalLayout(mode) {
  AppState.terminalLayout = mode;

  if (mode === 'broker') {
    switchView('broker');
  } else if (mode === 'split') {
    switchView('chart');
  } else {
    if (AppState.activeView !== 'monitor') {
      switchView('monitor');
    }
    const monitorGrid = document.querySelector('.monitor-grid');
    if (monitorGrid) monitorGrid.style.display = 'grid';
    setTimeout(() => syncBrokerStationLayout(true), 60);
  }
}
window.switchTerminalLayout = switchTerminalLayout;

// ============================================================================
// Live Market Scanner / Signal Tool Controls
// ============================================================================
function updateToolStatusUI(isActive) {
  AppState.toolActive = !!isActive;
  AppState.running = !!isActive;

  // Update Live Market Panel Status Badge
  const statusBadge = document.getElementById('market-tool-status');
  const statusText = document.getElementById('market-tool-status-text');
  if (statusBadge) {
    statusBadge.className = `tool-status-badge ${isActive ? 'active' : 'stopped'}`;
  }
  if (statusText) {
    statusText.textContent = isActive ? 'SCANNER ACTIVE' : 'SCANNER STOPPED';
  }

  // Update Start & Stop Buttons
  const btnStart = document.getElementById('btn-market-start');
  const btnStop = document.getElementById('btn-market-stop');
  if (btnStart) {
    if (isActive) btnStart.classList.add('active');
    else btnStart.classList.remove('active');
  }
  if (btnStop) {
    if (!isActive) btnStop.classList.add('active');
    else btnStop.classList.remove('active');
  }

  // Update Header Scanner Toggle Button
  const headerBtn = document.getElementById('scanner-btn');
  const headerIcon = document.getElementById('scanner-btn-icon');
  const headerText = document.getElementById('scanner-btn-text');
  if (headerBtn) {
    if (isActive) {
      headerBtn.classList.remove('paused');
      if (headerIcon) headerIcon.textContent = '⏸';
      if (headerText) headerText.textContent = 'Pause';
    } else {
      headerBtn.classList.add('paused');
      if (headerIcon) headerIcon.textContent = '▶';
      if (headerText) headerText.textContent = 'Resume';
    }
  }
}
window.updateToolStatusUI = updateToolStatusUI;

function startTool() {
  if (AppState.toolActive) {
    showToast('Market Scanner is already active', 'info');
    return;
  }
  updateToolStatusUI(true);
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_tool_active) {
    window.pywebview.api.set_tool_active(true).catch(e => console.debug('[TOOL] start error:', e));
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_engine) {
    window.pywebview.api.toggle_engine().catch(e => console.debug('[TOOL] toggle error:', e));
  }
  showToast('🟢 Live Market Scanner STARTED', 'success');
}
window.startTool = startTool;

function stopTool() {
  if (!AppState.toolActive) {
    showToast('Market Scanner is already stopped', 'info');
    return;
  }
  updateToolStatusUI(false);
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_tool_active) {
    window.pywebview.api.set_tool_active(false).catch(e => console.debug('[TOOL] stop error:', e));
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_engine) {
    window.pywebview.api.toggle_engine().catch(e => console.debug('[TOOL] toggle error:', e));
  }
  showToast('⏹ Live Market Scanner STOPPED', 'info');
}
window.stopTool = stopTool;

function toggleEngine() {
  if (AppState.toolActive) {
    stopTool();
  } else {
    startTool();
  }
}
window.toggleEngine = toggleEngine;

// ============================================================================
// Real-Time Broker Status & WebSocket Telemetry
// ============================================================================
window.onBrokerStatus = function(mode, text, latency) {
  const dot = document.getElementById('status-dot');
  const textEl = document.getElementById('status-text');
  const latencyEl = document.getElementById('latency-text');
  const btnConnect = document.getElementById('btn-broker-connect');
  const banner = document.getElementById('broker-connect-banner');

  if (!dot || !textEl) return;

  if (mode === 'connected') {
    dot.className = 'status-dot connected';
    textEl.textContent = 'Connected';
    if (latencyEl) {
      latencyEl.textContent = latency ? `${latency}ms` : '<10ms';
      latencyEl.className = 'latency-badge good';
    }
    if (btnConnect) {
      btnConnect.textContent = '🟢 Broker Linked (View)';
      btnConnect.className = 'btn-broker-login connected-mode';
      btnConnect.onclick = () => switchView('broker');
    }
    if (banner) banner.style.display = 'none';
    AppState.connected = true;
    startAutoStreamPrimer();
  } else if (mode === 'connecting') {
    dot.className = 'status-dot connecting';
    textEl.textContent = text || 'Connecting...';
    if (latencyEl) latencyEl.textContent = '';
    if (btnConnect) {
      btnConnect.textContent = '🔑 Connect Broker';
      btnConnect.className = 'btn-broker-login';
      btnConnect.onclick = () => switchView('broker');
    }
    if (banner) banner.style.display = 'flex';
    AppState.connected = false;
  } else {
    dot.className = 'status-dot';
    textEl.textContent = text || 'Disconnected';
    if (latencyEl) latencyEl.textContent = '';
    if (btnConnect) {
      btnConnect.textContent = '🔑 Connect Broker';
      btnConnect.className = 'btn-broker-login';
      btnConnect.onclick = () => switchView('broker');
    }
    if (banner) banner.style.display = 'flex';
    AppState.connected = false;
  }
};

// ============================================================================
// Real-Time Ticks & Market Watch Table (High-Frequency Batch Optimized)
// ============================================================================
function formatPriceCellContent(symbol, price, source, isOtc = true) {
  if (price === undefined || price === null || isNaN(price) || price <= 0.0001) {
    const isPairOtc = isOtc || (symbol && symbol.includes('(OTC)'));
    const safeSym = (symbol || '').replace(/'/g, "\\'");
    if (isPairOtc) {
      return `<span class="waiting-price-tag" onclick="event.stopPropagation(); selectActiveMarket('${safeSym}')" title="Auto-connecting live stream for ${safeSym}... (or click to switch chart)">Waiting for stream...</span>`;
    } else {
      return `<span class="standby-price-tag" onclick="event.stopPropagation(); selectActiveMarket('${safeSym}')" title="Click to open chart in Quotex terminal and activate live stream">Sync Chart 🔀</span>`;
    }
  }

  const formatted = formatPrice(symbol, price);
  const dir = AppState.priceDirections[symbol] || 'FLAT';
  let arrowHtml = '<span class="price-dir-arrow dir-flat">–</span>';
  let rateClass = 'price-value';

  if (dir === 'UP') {
    arrowHtml = '<span class="price-dir-arrow dir-up">▲</span>';
    rateClass += ' price-up';
  } else if (dir === 'DOWN') {
    arrowHtml = '<span class="price-dir-arrow dir-down">▼</span>';
    rateClass += ' price-down';
  } else {
    rateClass += ' price-flat';
  }

  let badgeHtml = '';

  if (source === 'real_market' || source === 'binance_spot') {
    badgeHtml = '<span class="source-badge source-real" title="Authentic Global Interbank Live Feed">REAL</span>';
  } else if (source === 'active_chart' || source === 'ws_subscription' || source === 'ws_stream' || source === 'ws_history') {
    badgeHtml = '<span class="source-badge source-live" title="Confirmed Live Quotex OTC Stream">LIVE</span>';
  } else if (source === 'instrument_object') {
    rateClass += ' price-est';
    badgeHtml = '<span class="source-badge source-est" title="Estimated from Instrument State">EST</span>';
  } else if (source === 'dom_tabscan') {
    rateClass += ' price-scan';
    badgeHtml = '<span class="source-badge source-scan" title="Estimated from Page Scan — Not a confirmed live feed">SCAN</span>';
  } else if (source && source !== 'unknown') {
    badgeHtml = `<span class="source-badge source-scan" title="Source: ${source}">${source.toUpperCase()}</span>`;
  }

  return `<div class="price-cell-wrapper"><span class="${rateClass}">${arrowHtml} ${formatted}</span>${badgeHtml}</div>`;
}

window.onBatchTicks = function(ticks) {
  if (!ticks) return;
  for (const [symbol, data] of Object.entries(ticks)) {
    const price = (typeof data === 'object' && data !== null && data.price !== undefined) ? data.price : data;
    const source = (typeof data === 'object' && data !== null && data.source) ? data.source : (AppState.priceSources[symbol] || 'unknown');

    const oldPrice = AppState.prices[symbol];
    if (oldPrice !== undefined && oldPrice !== price) {
      if (price > oldPrice) {
        AppState.priceDirections[symbol] = 'UP';
      } else if (price < oldPrice) {
        AppState.priceDirections[symbol] = 'DOWN';
      } else {
        AppState.priceDirections[symbol] = 'FLAT';
      }
    }
    AppState.prices[symbol] = price;
    if (source && source !== 'unknown') {
      AppState.priceSources[symbol] = source;
    }

    // Forward tick directly to Real-Time Interactive Live Chart
    if (window.LiveChartEngine && window.LiveChartEngine.activeSymbol === symbol) {
      window.LiveChartEngine.onLiveTick(symbol, price);
    }

    const row = document.getElementById(`row-${sanitizeId(symbol)}`);
    if (!row) continue;

    const priceCell = row.querySelector('.price-cell');
    if (priceCell) {
      priceCell.innerHTML = formatPriceCellContent(symbol, price, AppState.priceSources[symbol] || source, symbol.includes('(OTC)'));
      if (oldPrice !== undefined && oldPrice !== price) {
        const valEl = priceCell.querySelector('.price-value');
        if (valEl) {
          valEl.classList.remove('tick-pulse-up', 'tick-pulse-down');
          const pulseClass = price > oldPrice ? 'tick-pulse-up' : 'tick-pulse-down';
          requestAnimationFrame(() => {
            valEl.classList.add(pulseClass);
          });
        }
      }
    }
  }
};

window.onBatchPayouts = function(payouts) {
  if (!payouts) return;
  for (const [symbol, payout] of Object.entries(payouts)) {
    AppState.payouts[symbol] = payout;
    const badge = document.getElementById(`payout-${sanitizeId(symbol)}`);
    if (badge) {
      badge.textContent = `${payout}%`;
      let payoutClass = 'payout-mid';
      if (payout >= 85) payoutClass = 'payout-high';
      else if (payout < 80) payoutClass = 'payout-low';
      badge.className = `payout-badge ${payoutClass}`;
    }
  }
  if (window.LiveChartEngine && window.LiveChartEngine.activeSymbol) {
    window.LiveChartEngine.updateAssetMeta(window.LiveChartEngine.activeSymbol);
  }
};

window.onPriceTick = function(symbol, price, source = 'unknown') {
  const oldPrice = AppState.prices[symbol];
  if (oldPrice !== undefined && oldPrice !== price) {
    if (price > oldPrice) {
      AppState.priceDirections[symbol] = 'UP';
    } else if (price < oldPrice) {
      AppState.priceDirections[symbol] = 'DOWN';
    }
  }
  AppState.prices[symbol] = price;
  if (source && source !== 'unknown') {
    AppState.priceSources[symbol] = source;
  }

  // Forward tick directly to Real-Time Interactive Live Chart
  if (window.LiveChartEngine && window.LiveChartEngine.activeSymbol === symbol) {
    window.LiveChartEngine.onLiveTick(symbol, price);
  }

  // 1. Update Table row if present
  const row = document.getElementById(`row-${sanitizeId(symbol)}`);
  if (row) {
    const priceCell = row.querySelector('.price-cell');
    if (priceCell) {
      priceCell.innerHTML = formatPriceCellContent(symbol, price, AppState.priceSources[symbol] || source, symbol.includes('(OTC)'));
      if (oldPrice !== undefined && oldPrice !== price) {
        const valEl = priceCell.querySelector('.price-value');
        if (valEl) {
          valEl.classList.remove('tick-pulse-up', 'tick-pulse-down');
          const pulseClass = price > oldPrice ? 'tick-pulse-up' : 'tick-pulse-down';
          requestAnimationFrame(() => {
            valEl.classList.add(pulseClass);
          });
        }
      }
    }
  }

  // 2. Update Heatmap tile if present
  const tilePriceEl = document.getElementById(`tile-price-${sanitizeId(symbol)}`);
  if (tilePriceEl) {
    const dirArrow = price > oldPrice ? '▲' : (price < oldPrice ? '▼' : '●');
    tilePriceEl.className = `heatmap-price ${price > oldPrice ? 'price-up' : (price < oldPrice ? 'price-down' : '')}`;
    tilePriceEl.textContent = `${dirArrow} ${formatPrice(symbol, price)}`;
  }

  // 3. Update active signal pip tracker for this symbol immediately
  updateSignalPipsForSymbol(symbol, price);
};

window.onPayoutUpdate = function(symbol, payout) {
  AppState.payouts[symbol] = payout;
  let payoutClass = 'payout-mid';
  if (payout >= 85) payoutClass = 'payout-high';
  else if (payout < 80) payoutClass = 'payout-low';

  const badge = document.getElementById(`payout-${sanitizeId(symbol)}`);
  if (badge) {
    badge.textContent = `${payout}%`;
    badge.className = `payout-badge ${payoutClass}`;
  }

  const tileBadge = document.querySelector(`#heatmap-tile-${sanitizeId(symbol)} .payout-badge`);
  if (tileBadge) {
    tileBadge.textContent = `${payout}%`;
    tileBadge.className = `payout-badge ${payoutClass}`;
  }

  if (window.LiveChartEngine && window.LiveChartEngine.activeSymbol === symbol) {
    window.LiveChartEngine.updateAssetMeta(symbol);
  }
};

window.onCandleCompleted = function(payload) {
  if (!payload) return;
  if (window.LiveChartEngine && window.LiveChartEngine.onCandleCompleted) {
    window.LiveChartEngine.onCandleCompleted(payload);
  }
};

function updateSignalPipsForSymbol(symbol, price) {
  if (!price || !AppState.signals) return;
  AppState.signals.forEach(sig => {
    if (sig.asset_symbol !== symbol) return;
    if (sig.status === 'WIN' || sig.status === 'LOSS' || sig.status === 'DRAW') return;
    if (sig.entry_price == null) return;

    const isCall = (sig.direction || '').toUpperCase() === 'CALL';
    const diff = price - sig.entry_price;
    const isHighOrJpy = symbol.includes('JPY') || price > 20;
    const mult = isHighOrJpy ? 100 : 10000;
    const signedPips = isCall ? (diff * mult) : (-diff * mult);

    let pipBadgeClass = 'pip-badge pip-atm';
    let pipBadgeText = '● 0.0 pips ATM ⚪';
    if (signedPips > 0.05) {
      pipBadgeClass = 'pip-badge pip-itm';
      pipBadgeText = `▲ +${signedPips.toFixed(1)} pips ITM 🟢`;
    } else if (signedPips < -0.05) {
      pipBadgeClass = 'pip-badge pip-otm';
      pipBadgeText = `▼ ${signedPips.toFixed(1)} pips OTM 🔴`;
    }

    const pipEl = document.getElementById(`pip-track-${sig.id}`);
    const splitPipEl = document.getElementById(`split-pip-track-${sig.id}`);
    if (pipEl) {
      pipEl.className = pipBadgeClass;
      pipEl.textContent = pipBadgeText;
    }
    if (splitPipEl) {
      splitPipEl.className = pipBadgeClass;
      splitPipEl.textContent = pipBadgeText;
    }
  });
}

function setMarketViewMode(mode) {
  AppState.marketViewMode = mode;
  const btnTable = document.getElementById('btn-market-table') || document.getElementById('btn-view-table');
  const btnHeatmap = document.getElementById('btn-market-heatmap') || document.getElementById('btn-view-heatmap');
  const tableContainer = document.getElementById('markets-table-container') || document.getElementById('markets-table-scroll');
  const heatmapContainer = document.getElementById('markets-heatmap-grid');

  if (btnTable) btnTable.classList.toggle('active', mode === 'table');
  if (btnHeatmap) btnHeatmap.classList.toggle('active', mode === 'heatmap');

  if (mode === 'heatmap') {
    if (tableContainer) tableContainer.style.display = 'none';
    if (heatmapContainer) heatmapContainer.style.display = 'grid';
    renderMarketHeatmap();
  } else {
    if (tableContainer) tableContainer.style.display = 'block';
    if (heatmapContainer) heatmapContainer.style.display = 'none';
    renderMarketsTable();
  }
}
window.setMarketViewMode = setMarketViewMode;

function setPayoutFilter(minPayout) {
  if (AppState.marketPayoutFilter === minPayout) {
    AppState.marketPayoutFilter = 0; // toggle off
  } else {
    AppState.marketPayoutFilter = minPayout;
  }

  const btn90 = document.getElementById('payout-filter-90');
  const btn85 = document.getElementById('payout-filter-85');
  if (btn90) btn90.classList.toggle('active', AppState.marketPayoutFilter === 90);
  if (btn85) btn85.classList.toggle('active', AppState.marketPayoutFilter === 85);

  refreshMarketsView();
}
window.setPayoutFilter = setPayoutFilter;

function refreshMarketsView(assets) {
  if (assets && Array.isArray(assets)) {
    AppState.allAssets = assets;
  }
  if (AppState.marketViewMode === 'heatmap') {
    renderMarketHeatmap();
  } else {
    renderMarketsTable();
  }
}
window.refreshMarketsView = refreshMarketsView;

window.onAssetsUpdated = function(assets) {
  if (!assets || !Array.isArray(assets)) return;
  AppState.allAssets = assets;
  AppState.precisions = AppState.precisions || {};
  assets.forEach(a => {
    if (a.symbol && a.precision !== undefined) {
      AppState.precisions[a.symbol] = a.precision;
    }
  });
  updateQuickPairSelector(assets);
  refreshMarketsView();
};

function filterMarketCategory(category) {
  AppState.marketCategory = category;
  document.querySelectorAll('.cat-pill').forEach(btn => btn.classList.remove('active'));
  const catId = category.toLowerCase();
  const activeBtn = document.getElementById(`cat-tab-${catId === 'favorites' ? 'favs' : catId}`);
  if (activeBtn) activeBtn.classList.add('active');
  refreshMarketsView();
}
window.filterMarketCategory = filterMarketCategory;

function handleMarketSearch(query) {
  AppState.marketSearchQuery = (query || '').trim().toLowerCase();
  refreshMarketsView();
}
window.handleMarketSearch = handleMarketSearch;

function updateQuickPairSelector(assets) {
  const quickSelect = document.getElementById('quick-pair-select');
  if (!quickSelect || !assets || assets.length === 0) return;
  const currentVal = quickSelect.value;
  quickSelect.innerHTML = '';
  assets.forEach(a => {
    const opt = document.createElement('option');
    opt.value = a.symbol;
    opt.textContent = a.symbol;
    opt.style.background = '#0e1420';
    opt.style.color = '#fff';
    quickSelect.appendChild(opt);
  });
  if (currentVal && Array.from(quickSelect.options).some(o => o.value === currentVal)) {
    quickSelect.value = currentVal;
  }
}

function getAssetIcon(symbol, category) {
  if (category === 'crypto' || symbol.includes('BTC') || symbol.includes('ETH') || symbol.includes('SOL') || symbol.includes('LTC') || symbol.includes('XRP')) return '🪙';
  if (category === 'commodities' || symbol.includes('Gold') || symbol.includes('Silver') || symbol.includes('Brent') || symbol.includes('Crude')) return '🛢️';
  if (symbol.includes('USD') || symbol.includes('EUR') || symbol.includes('GBP') || symbol.includes('JPY') || symbol.includes('INR') || symbol.includes('BRL')) return '💱';
  return '📈';
}

function getAssignedStrategiesForAsset(symbol) {
  const isOtc = symbol.includes('(OTC)') || symbol.includes('_otc');
  const symClean = symbol.replace(' (OTC)', '').replace('_otc', '').replace('/', '').toUpperCase();
  return (AppState.strategies || []).filter(s => {
    if (!s.enabled) return false;
    const scope = Array.isArray(s.assets) ? s.assets : ['ALL_MARKETS'];
    if (scope.includes('ALL_MARKETS') || scope.includes('ALL')) return true;
    if (scope.includes('ALL_OTC') && isOtc) return true;
    if (scope.includes('ALL_REAL') && !isOtc) return true;
    if (scope.includes(symbol)) return true;
    return scope.some(item => item.replace(' (OTC)', '').replace('_otc', '').replace('/', '').toUpperCase() === symClean);
  });
}
window.getAssignedStrategiesForAsset = getAssignedStrategiesForAsset;

function renderMarketsTable(assets) {
  if (assets && Array.isArray(assets)) {
    AppState.allAssets = assets;
  }

  const tbody = document.getElementById('markets-table-body');
  if (!tbody) return;

  const all = AppState.allAssets || [];
  const cat = AppState.marketCategory || 'ALL';
  const query = AppState.marketSearchQuery || '';

  const filtered = all.filter(asset => {
    // 1. Favorites filter
    if (cat === 'FAVORITES') {
      if (!AppState.favorites.has(asset.symbol)) return false;
    }
    // 2. Category filter
    else if (cat === 'CURRENCIES') {
      if (asset.category && asset.category !== 'currencies') return false;
    } else if (cat === 'REAL') {
      if (asset.is_otc || asset.symbol.includes('(OTC)')) return false;
    } else if (cat === 'OTC') {
      if (!asset.is_otc && !asset.symbol.includes('(OTC)')) return false;
    } else if (cat === 'CRYPTO') {
      if (asset.category !== 'crypto') return false;
    } else if (cat === 'COMMODITIES') {
      if (asset.category !== 'commodities') return false;
    }

    // 3. Search query filter
    if (query) {
      const symClean = asset.symbol.toLowerCase().replace(/[^a-z0-9]/g, '');
      const wsClean = (asset.ws_asset || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      const qClean = query.replace(/[^a-z0-9]/g, '');
      if (!symClean.includes(qClean) && !wsClean.includes(qClean)) return false;
    }

    // 4. Payout filter
    if (AppState.marketPayoutFilter > 0) {
      const p = AppState.payouts[asset.symbol] || 0;
      if (p < AppState.marketPayoutFilter) return false;
    }

    return true;
  });

  const watchedEl = document.getElementById('stat-markets-watched');
  if (watchedEl) {
    const totalCount = all.length;
    const watchedCount = all.filter(a => AppState.watchedMarkets[a.symbol] !== false).length;
    watchedEl.textContent = totalCount > 0 ? `${watchedCount} / ${totalCount}` : '104';
  }

  tbody.innerHTML = '';

  if (filtered.length === 0) {
    const emptyTr = document.createElement('tr');
    emptyTr.innerHTML = `
      <td colspan="5" style="text-align: center; padding: 36px 16px; color: var(--text-muted); font-size: 12px;">
        ${cat === 'FAVORITES' ? 'No favorite markets selected yet. Click the star (☆) next to any pair to bookmark it!' : `No trade pairs match "${query || cat}".`}
      </td>
    `;
    tbody.appendChild(emptyTr);
    return;
  }

  // Sort assets: actively streaming assets (with confirmed prices) ALWAYS appear first!
  filtered.sort((a, b) => {
    const isFavA = AppState.favorites.has(a.symbol) ? 1 : 0;
    const isFavB = AppState.favorites.has(b.symbol) ? 1 : 0;
    if (isFavA !== isFavB) return isFavB - isFavA;

    const hasPriceA = (AppState.prices[a.symbol] !== undefined && AppState.prices[a.symbol] > 0.0001) ? 1 : 0;
    const hasPriceB = (AppState.prices[b.symbol] !== undefined && AppState.prices[b.symbol] > 0.0001) ? 1 : 0;
    if (hasPriceA !== hasPriceB) return hasPriceB - hasPriceA;

    const otcA = (a.is_otc || a.symbol.includes('(OTC)')) ? 1 : 0;
    const otcB = (b.is_otc || b.symbol.includes('(OTC)')) ? 1 : 0;
    if (otcA !== otcB) return otcB - otcA;
    return 0;
  });

  filtered.forEach(asset => {
    const symbol = asset.symbol;
    const safeSym = symbol.replace(/'/g, "\\'");
    const isOtc = asset.is_otc || symbol.includes('(OTC)');
    const payout = AppState.payouts[symbol];
    const isWatched = AppState.watchedMarkets[symbol] !== false; // Default true
    const isFav = AppState.favorites.has(symbol);

    let payoutText = '<span class="waiting-tag">--%</span>';
    let payoutClass = 'payout-none';
    if (payout !== undefined && payout !== null && payout > 0) {
      payoutText = `${payout}%`;
      if (payout >= 85) payoutClass = 'payout-high';
      else if (payout < 80) payoutClass = 'payout-low';
      else payoutClass = 'payout-mid';
    }

    const priceVal = AppState.prices[symbol];
    const priceSrc = AppState.priceSources[symbol] || 'unknown';
    const currentPriceHtml = formatPriceCellContent(symbol, priceVal, priceSrc, isOtc);
    const assetIcon = getAssetIcon(symbol, asset.category);

    const badgeTag = isOtc
      ? '<span class="pair-badge-sub badge-otc">OTC 24/7</span>'
      : '<span class="pair-badge-sub badge-real">INTERBANK</span>';

    const activeStrats = getAssignedStrategiesForAsset(symbol);
    const stratBadgeHtml = activeStrats.length > 0
      ? `<span class="pair-badge-sub" style="color: var(--cyan-bright); border-color: rgba(0, 240, 255, 0.3); background: rgba(0, 240, 255, 0.08); cursor: pointer;" title="Active Strategies (${activeStrats.length}): ${escapeHtml(activeStrats.map(s => s.name).join(', '))} · Click to view in Strategy Lab" onclick="event.stopPropagation(); switchView('strategies');">🎯 ${activeStrats.length} strat${activeStrats.length > 1 ? 's' : ''}</span>`
      : '';

    const tr = document.createElement('tr');
    tr.id = `row-${sanitizeId(symbol)}`;
    tr.className = 'market-row';
    tr.title = `Click to switch Quotex terminal chart to ${symbol}`;
    if (AppState.selectedMarket === symbol) {
      tr.classList.add('active-market-row');
    }
    tr.onclick = (e) => {
      if (e.target && (e.target.type === 'checkbox' || e.target.classList.contains('custom-checkbox') || e.target.classList.contains('btn-star-fav'))) {
        return;
      }
      selectActiveMarket(symbol);
    };

    tr.innerHTML = `
      <td style="text-align: center;" onclick="event.stopPropagation()">
        <button type="button" class="btn-star-fav ${isFav ? 'is-favorite' : ''}" onclick="toggleFavorite('${safeSym}', event)" title="${isFav ? 'Remove from favorites' : 'Add to favorites'}">
          ${isFav ? '★' : '☆'}
        </button>
      </td>
      <td style="text-align: center;" onclick="event.stopPropagation()">
        <input type="checkbox" class="custom-checkbox" ${isWatched ? 'checked' : ''} onchange="handleMarketToggle('${safeSym}', this.checked)">
      </td>
      <td>
        <div class="pair-meta-cell">
          <div class="pair-icon-pill">${assetIcon}</div>
          <div class="pair-name-group">
            <span class="pair-title">${symbol}</span>
            <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
              ${badgeTag}
              ${stratBadgeHtml}
            </div>
          </div>
        </div>
      </td>
      <td class="price-cell">
        ${currentPriceHtml}
      </td>
      <td>
        <span class="payout-badge ${payoutClass}" id="payout-${sanitizeId(symbol)}">${payoutText}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMarketHeatmap(assets) {
  if (assets && Array.isArray(assets)) {
    AppState.allAssets = assets;
  }

  const container = document.getElementById('markets-heatmap-grid');
  if (!container) return;

  const all = AppState.allAssets || [];
  const cat = AppState.marketCategory || 'ALL';
  const query = AppState.marketSearchQuery || '';
  const minPayout = AppState.marketPayoutFilter || 0;

  const filtered = all.filter(asset => {
    if (cat === 'FAVORITES') {
      if (!AppState.favorites.has(asset.symbol)) return false;
    } else if (cat === 'CURRENCIES') {
      if (asset.category && asset.category !== 'currencies') return false;
    } else if (cat === 'REAL') {
      if (asset.is_otc || asset.symbol.includes('(OTC)')) return false;
    } else if (cat === 'OTC') {
      if (!asset.is_otc && !asset.symbol.includes('(OTC)')) return false;
    } else if (cat === 'CRYPTO') {
      if (asset.category !== 'crypto') return false;
    } else if (cat === 'COMMODITIES') {
      if (asset.category !== 'commodities') return false;
    }

    if (query) {
      const symClean = asset.symbol.toLowerCase().replace(/[^a-z0-9]/g, '');
      const wsClean = (asset.ws_asset || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      const qClean = query.replace(/[^a-z0-9]/g, '');
      if (!symClean.includes(qClean) && !wsClean.includes(qClean)) return false;
    }

    if (minPayout > 0) {
      const p = AppState.payouts[asset.symbol] || 0;
      if (p < minPayout) return false;
    }

    return true;
  });

  filtered.sort((a, b) => {
    const isFavA = AppState.favorites.has(a.symbol) ? 1 : 0;
    const isFavB = AppState.favorites.has(b.symbol) ? 1 : 0;
    if (isFavA !== isFavB) return isFavB - isFavA;

    const pA = AppState.payouts[a.symbol] || 0;
    const pB = AppState.payouts[b.symbol] || 0;
    if (pB !== pA) return pB - pA;

    const hasPriceA = (AppState.prices[a.symbol] !== undefined && AppState.prices[a.symbol] > 0.0001) ? 1 : 0;
    const hasPriceB = (AppState.prices[b.symbol] !== undefined && AppState.prices[b.symbol] > 0.0001) ? 1 : 0;
    return hasPriceB - hasPriceA;
  });

  container.innerHTML = '';

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 36px 16px; color: var(--text-muted); font-size: 12px;">
        No trade pairs match criteria (${minPayout > 0 ? `Payout >= ${minPayout}%, ` : ''}${cat}).
      </div>
    `;
    return;
  }

  filtered.forEach(asset => {
    const symbol = asset.symbol;
    const isOtc = asset.is_otc || symbol.includes('(OTC)');
    const payout = AppState.payouts[symbol];
    const isFav = AppState.favorites.has(symbol);
    const price = AppState.prices[symbol];
    const priceDir = AppState.priceDirections[symbol];
    const priceSrc = AppState.priceSources[symbol] || (isOtc ? 'Quotex OTC' : 'Interbank');

    let payoutTierClass = 'payout-tier-mid';
    let payoutText = '--%';
    if (payout !== undefined && payout !== null && payout > 0) {
      payoutText = `${payout}%`;
      if (payout >= 90) payoutTierClass = 'payout-tier-ultra';
      else if (payout >= 85) payoutTierClass = 'payout-tier-high';
      else if (payout < 80) payoutTierClass = 'payout-tier-low';
    }

    const dirArrow = priceDir === 'UP' ? '▲' : (priceDir === 'DOWN' ? '▼' : '●');
    const dirClass = priceDir === 'UP' ? 'price-up' : (priceDir === 'DOWN' ? 'price-down' : '');
    const priceStr = price ? formatPrice(symbol, price) : 'Streaming...';

    const activeStrats = getAssignedStrategiesForAsset(symbol);
    const stratTag = activeStrats.length > 0
      ? `<span class="heatmap-strat-tag" title="${escapeHtml(activeStrats.map(s => s.name).join(', '))}">🎯 ${activeStrats.length}</span>`
      : '';

    const tile = document.createElement('div');
    tile.className = `heatmap-tile ${payoutTierClass} ${AppState.selectedMarket === symbol ? 'active-tile' : ''}`;
    tile.id = `heatmap-tile-${sanitizeId(symbol)}`;
    tile.onclick = () => selectActiveMarket(symbol);

    tile.innerHTML = `
      <div class="heatmap-tile-top">
        <div class="heatmap-symbol-group">
          <span class="heatmap-icon">${getAssetIcon(symbol, asset.category)}</span>
          <span class="heatmap-symbol">${escapeHtml(symbol)}</span>
        </div>
        <div class="heatmap-tags">
          <span class="payout-badge ${payout >= 85 ? 'payout-high' : 'payout-mid'}">${payoutText}</span>
        </div>
      </div>
      <div class="heatmap-tile-mid">
        <span class="heatmap-price ${dirClass}" id="tile-price-${sanitizeId(symbol)}">
          ${dirArrow} ${priceStr}
        </span>
        <span class="heatmap-type-tag">${isOtc ? 'OTC' : 'REAL'}</span>
      </div>
      <div class="heatmap-tile-bottom">
        <span class="heatmap-source-label">${escapeHtml(priceSrc)}</span>
        ${stratTag}
      </div>
    `;
    container.appendChild(tile);
  });
}
window.renderMarketHeatmap = renderMarketHeatmap;

function selectActiveMarket(symbol) {
  if (!symbol) return;
  AppState.selectedMarket = symbol;
  document.querySelectorAll('#markets-table-body tr').forEach(r => r.classList.remove('active-market-row'));
  const row = document.getElementById(`row-${sanitizeId(symbol)}`);
  if (row) {
    row.classList.add('active-market-row');
    const priceCell = row.querySelector('.price-cell');
    if (priceCell && (!AppState.prices[symbol] || AppState.prices[symbol] <= 0.0001)) {
      priceCell.innerHTML = '<span class="standby-price-tag" style="color:var(--cyan-bright);">Opening chart...</span>';
    }
  }

  document.querySelectorAll('.heatmap-tile').forEach(t => t.classList.remove('active-tile'));
  const tile = document.getElementById(`heatmap-tile-${sanitizeId(symbol)}`);
  if (tile) tile.classList.add('active-tile');

  // Update quick selector if present
  const quickSelect = document.getElementById('quick-pair-select');
  if (quickSelect) quickSelect.value = symbol;

  console.log('[UI] Switching active market to:', symbol);
  if (window.TradePulseChart) {
    window.TradePulseChart.open(symbol, '1M');
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.switch_pair) {
    window.pywebview.api.switch_pair(symbol);
  }
}
window.selectActiveMarket = selectActiveMarket;
window.switchPairDirect = selectActiveMarket;

window.switchChartTf = function(tf) {
  document.querySelectorAll('.btn-chart-tf').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`chart-tf-${tf.toLowerCase()}`);
  if (btn) btn.classList.add('active');
  if (window.TradePulseChart) {
    window.TradePulseChart.open(window.TradePulseChart.activeSymbol || 'EUR/USD (OTC)', tf);
  }
};

window.closeChartDrawer = function() {
  if (window.TradePulseChart) {
    window.TradePulseChart.close();
  }
};

function handleMarketToggle(symbol, isChecked) {
  AppState.watchedMarkets[symbol] = isChecked;
  localStorage.setItem('tradepulse_watched_markets', JSON.stringify(AppState.watchedMarkets));
  if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_asset_watch) {
    window.pywebview.api.toggle_asset_watch(symbol, isChecked);
  }
}

function toggleAllMarkets(masterEl) {
  const isChecked = masterEl.checked;
  const checkboxes = document.querySelectorAll('#markets-table-body .custom-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = isChecked;
  });
  for (const item of AppState.allAssets) {
    AppState.watchedMarkets[item.symbol] = isChecked;
  }
  localStorage.setItem('tradepulse_watched_markets', JSON.stringify(AppState.watchedMarkets));
}

// ============================================================================
// Confirmed VIP Signals Feed & Active Countdown Progress
// ============================================================================
window.onSignalFired = function(signal) {
  if (!signal.id) signal.id = 'sig_' + Date.now();
  if (!signal.created_at) signal.created_at = new Date().toISOString();
  if (!signal.duration_minutes) signal.duration_minutes = 2;

  // Clear any active pre-signal banner for this asset
  if (AppState.preSignals) {
    AppState.preSignals = AppState.preSignals.filter(p => p.symbol !== signal.asset_symbol);
  }

  const existingIdx = AppState.signals.findIndex(s => s.id === signal.id);
  if (existingIdx !== -1) {
    AppState.signals[existingIdx] = signal;
  } else {
    AppState.signals.unshift(signal);
  }

  SoundEngine.playChime(signal.direction.toUpperCase() === 'CALL');
  VoiceEngine.announceSignal(signal);
  renderSignalsFeed();

  if (AppState.activeView === 'history') {
    renderHistoryTable();
  }

  // Increment today's stats
  AppState.stats.total = (AppState.stats.total || 0) + 1;
  const statSigEl = document.getElementById('stat-signals');
  if (statSigEl) statSigEl.textContent = AppState.stats.total;
};

window.onPreSignal = function(pre) {
  if (!AppState.preAlertsEnabled) return;
  if (!AppState.preSignals) AppState.preSignals = [];

  const existingIdx = AppState.preSignals.findIndex(p => p.symbol === pre.symbol);
  if (existingIdx !== -1) {
    AppState.preSignals[existingIdx] = pre;
  } else {
    AppState.preSignals.unshift(pre);
  }
  VoiceEngine.announcePreSignal(pre);
  renderSignalsFeed();
};

window.onTradeOutcome = function(signal) {
  const idx = AppState.signals.findIndex(s => s.id === signal.id);
  if (idx !== -1) {
    AppState.signals[idx] = signal;
  } else {
    AppState.signals.unshift(signal);
  }
  renderSignalsFeed();

  if (AppState.activeView === 'history') {
    renderHistoryTable();
  }

  // Refresh performance stats from backend & update leaderboard
  if (window.pywebview && window.pywebview.api) {
    if (window.pywebview.api.get_performance_stats) {
      window.pywebview.api.get_performance_stats().then(stats => {
        AppState.stats = stats;
        const winRateEl = document.getElementById('stat-win-rate');
        if (winRateEl) winRateEl.textContent = `${stats.win_rate}%`;
        loadStrategyLeaderboard();
      });
    }
    if (window.pywebview.api.get_risk_session_metrics) {
      window.pywebview.api.get_risk_session_metrics().then(metrics => {
        AppState.riskMetrics = metrics;
        if (typeof updateRiskMetricsUI === 'function') updateRiskMetricsUI(metrics);
        if (typeof updateSafeguardsStrip === 'function') updateSafeguardsStrip();
      });
    }
  }
};

function renderSignalsFeed() {
  const feed = document.getElementById('signals-feed');
  const emptyCard = document.getElementById('empty-feed-card');
  if (!feed) return;

  const hasPreSignals = AppState.preSignals && AppState.preSignals.length > 0;
  if (AppState.signals.length === 0 && !hasPreSignals) {
    if (emptyCard) emptyCard.style.display = 'flex';
    return;
  }

  if (emptyCard) emptyCard.style.display = 'none';
  feed.querySelectorAll('.signal-card, .pre-signal-banner').forEach(c => c.remove());

  // 1. Render Pre-Signal Early Warning Banners at top
  if (AppState.preAlertsEnabled && AppState.preSignals) {
    AppState.preSignals.forEach(pre => {
      const isCall = (pre.direction || '').toUpperCase() === 'CALL';
      const dirBadge = isCall ? '<span class="pre-dir-call">CALL (BUY) 🟢</span>' : '<span class="pre-dir-put">PUT (SELL) 🔴</span>';
      const symSlug = pre.symbol.replace(/[^a-zA-Z0-9]/g, '_');
      let preRiskHtml = '';
      if (AppState.advancedFilters?.risk_manager?.enabled) {
        const nextStake = AppState.riskMetrics?.next_recommended_stake || AppState.advancedFilters.risk_manager.base_stake || 10;
        const step = AppState.riskMetrics?.current_martingale_step || 1;
        preRiskHtml = `<span>·</span><span class="signal-risk-badge" style="font-size: 10px; padding: 2px 6px;">💰 Stake: $${nextStake.toFixed(0)}${step > 1 ? ' (Step ' + step + ')' : ''}</span>`;
      }

      const banner = document.createElement('div');
      banner.className = 'pre-signal-banner';
      banner.id = `pre-banner-${symSlug}`;
      banner.innerHTML = `
        <div class="pre-signal-header">
          <div class="pre-signal-badge">
            <span>⚡ PRE-ALERT: GET READY</span>
          </div>
          <div class="pre-countdown-badge" id="pre-timer-${symSlug}">
            ⏳ ${pre.remaining_seconds || 15}s
          </div>
        </div>
        <div class="pre-signal-body">
          <strong>${escapeHtml(pre.symbol)}</strong>
          <span>·</span>
          ${dirBadge}
          <span>·</span>
          <span style="font-size: 11px; opacity: 0.85;">${escapeHtml(pre.strategy_name || '')}</span>
          ${preRiskHtml}
        </div>
        <div style="font-size: 10px; color: var(--text-dim); margin-top: 4px;">
          <i>Open pair & set stake in Quotex. Official entry triggers at 00s candle close.</i>
        </div>
      `;
      feed.appendChild(banner);
    });
  }

  // 2. Render Confirmed Signals
  AppState.signals.slice(0, 25).forEach(sig => {
    const isCall = sig.direction.toUpperCase() === 'CALL';
    const cardClass = isCall ? 'sig-call' : 'sig-put';
    const arrow = isCall ? '▲ CALL' : '▼ PUT';
    const isActive = sig.status !== 'WIN' && sig.status !== 'LOSS' && sig.status !== 'DRAW';

    let extraBadgesHtml = '';
    if (sig.stake) {
      const stepLabel = sig.martingale_step && sig.martingale_step > 1 ? ` (Step ${sig.martingale_step})` : '';
      extraBadgesHtml += `<span class="signal-risk-badge" title="Recommended Position Sizing">💰 $${sig.stake}${stepLabel}</span>`;
    } else if (AppState.advancedFilters?.risk_manager?.enabled) {
      const nextStake = AppState.riskMetrics?.next_recommended_stake || AppState.advancedFilters.risk_manager.base_stake || 10;
      const step = AppState.riskMetrics?.current_martingale_step || 1;
      const stepLabel = step > 1 ? ` (Step ${step})` : '';
      extraBadgesHtml += `<span class="signal-risk-badge" title="Recommended Position Sizing">💰 $${nextStake.toFixed(0)}${stepLabel}</span>`;
    }
    if (sig.ev !== undefined && sig.ev !== null) {
      extraBadgesHtml += `<span class="signal-ev-badge" title="Mathematical Expected Value Edge">🧮 EV +$${sig.ev.toFixed(2)}</span>`;
    }

    let outcomeBadgeHtml = '';
    if (sig.status === 'WIN') {
      outcomeBadgeHtml = `<span class="payout-badge payout-high">WIN ✅</span>`;
    } else if (sig.status === 'LOSS') {
      outcomeBadgeHtml = `<span class="payout-badge payout-low">LOSS ❌</span>`;
    } else if (sig.status === 'DRAW') {
      outcomeBadgeHtml = `<span class="payout-badge payout-mid">DRAW ⚪</span>`;
    } else {
      outcomeBadgeHtml = `<span class="latency-badge good" id="timer-${sig.id}">⏳ Calculating...</span>`;
    }

    const radialHtml = isActive ? `
      <div class="radial-timer-wrapper" title="Remaining Expiry">
        <svg class="radial-timer-svg" width="34" height="34" viewBox="0 0 34 34">
          <circle class="radial-timer-bg" cx="17" cy="17" r="14"></circle>
          <circle class="radial-timer-ring" id="radial-ring-${sig.id}" cx="17" cy="17" r="14" stroke-dasharray="87.96" stroke-dashoffset="0"></circle>
        </svg>
        <span class="radial-timer-text" id="radial-text-${sig.id}">--</span>
      </div>
    ` : '';

    const pipBadgeHtml = isActive ? `<span class="pip-badge pip-atm" id="pip-track-${sig.id}">● 0.0 pips ATM ⚪</span>` : '';

    const card = document.createElement('div');
    card.className = `signal-card ${cardClass}`;
    card.id = `signal-card-${sig.id}`;
    card.innerHTML = `
      <div class="signal-card-header">
        <div class="signal-asset-title">
          <span>${escapeHtml(sig.asset_symbol)}</span>
          <span class="signal-dir-badge">${arrow}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          ${extraBadgesHtml}
          <span class="confluence-pill">${escapeHtml(sig.strategy_name || 'Confluence VIP')}</span>
          <button class="btn-chart-peek" title="Inspect Candlestick Chart & S/R Pivots">📈</button>
        </div>
      </div>

      <div class="signal-meta-row">
        <div class="signal-meta-item">
          <span class="signal-meta-label">Strike Price</span>
          <span class="signal-meta-val">${sig.entry_price}</span>
        </div>
        <div class="signal-meta-item">
          <span class="signal-meta-label">Payout</span>
          <span class="signal-meta-val" style="color: var(--emerald);">${sig.live_payout != null ? sig.live_payout + '%' : '85%'}</span>
        </div>
        <div class="signal-meta-item">
          <span class="signal-meta-label">Setup Score</span>
          <span class="signal-meta-val" style="color: var(--amber);">${sig.confidence || 92}%</span>
        </div>
      </div>

      <div class="signal-timer-bar">
        <div class="signal-timer-progress" id="progress-${sig.id}" style="width: 100%;"></div>
      </div>

      <div class="signal-footer-row">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span>Expiry: ${sig.duration_minutes || 2}m</span>
          ${pipBadgeHtml}
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${radialHtml}
          ${outcomeBadgeHtml}
        </div>
      </div>
    `;

    const peekBtn = card.querySelector('.btn-chart-peek');
    if (peekBtn) {
      peekBtn.onclick = (e) => {
        e.stopPropagation();
        if (window.TradePulseChart) {
          window.TradePulseChart.open(sig.asset_symbol, '1M', sig);
        }
      };
    }

    feed.appendChild(card);
  });

  syncSplitSignalsFeed();
  updateActiveCountdowns();
}

function syncSplitSignalsFeed() {
  const container = document.getElementById('split-signals-feed');
  if (!container) return;

  const activeSignals = AppState.signals.filter(s => s.status !== 'WIN' && s.status !== 'LOSS' && s.status !== 'DRAW');
  const countBadge = document.getElementById('split-radar-count');
  if (countBadge) {
    countBadge.textContent = `${activeSignals.length} Live`;
  }

  const displayList = (activeSignals.length > 0 ? activeSignals : AppState.signals).slice(0, 15);

  if (displayList.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 48px 16px; color: var(--text-dim); font-size: 12px; line-height: 1.6;">
        <span style="font-size: 24px; display: block; margin-bottom: 8px;">📡</span>
        Scanning all pairs with OTC Confluence Guard...<br>
        High-payout signals appear here instantly for manual Quotex execution.
      </div>
    `;
    return;
  }

  container.innerHTML = '';

  displayList.forEach(sig => {
    const isCall = (sig.direction || '').toUpperCase() === 'CALL';
    const cardClass = isCall ? 'sig-call' : 'sig-put';
    const arrow = isCall ? '▲ CALL (BUY)' : '▼ PUT (SELL)';
    const isActive = sig.status !== 'WIN' && sig.status !== 'LOSS' && sig.status !== 'DRAW';

    let outcomeBadgeHtml = '';
    if (sig.status === 'WIN') {
      outcomeBadgeHtml = `<span class="payout-badge payout-high">WIN ✅</span>`;
    } else if (sig.status === 'LOSS') {
      outcomeBadgeHtml = `<span class="payout-badge payout-low">LOSS ❌</span>`;
    } else if (sig.status === 'DRAW') {
      outcomeBadgeHtml = `<span class="payout-badge payout-mid">DRAW ⚪</span>`;
    } else {
      outcomeBadgeHtml = `<span class="latency-badge good" id="split-timer-${sig.id}">⏳ Calculating...</span>`;
    }

    const radialHtml = isActive ? `
      <div class="radial-timer-wrapper" title="Remaining Expiry">
        <svg class="radial-timer-svg" width="34" height="34" viewBox="0 0 34 34">
          <circle class="radial-timer-bg" cx="17" cy="17" r="14"></circle>
          <circle class="radial-timer-ring" id="split-radial-ring-${sig.id}" cx="17" cy="17" r="14" stroke-dasharray="87.96" stroke-dashoffset="0"></circle>
        </svg>
        <span class="radial-timer-text" id="split-radial-text-${sig.id}">--</span>
      </div>
    ` : '';

    const pipBadgeHtml = isActive ? `<span class="pip-badge pip-atm" id="split-pip-track-${sig.id}">● 0.0 pips ATM ⚪</span>` : '';

    const card = document.createElement('div');
    card.className = `signal-card ${cardClass}`;
    card.id = `split-card-${sig.id}`;
    card.style.cursor = 'pointer';
    card.title = `Click to switch Quotex terminal chart to ${sig.asset_symbol}`;
    card.onclick = () => selectActiveMarket(sig.asset_symbol);

    card.innerHTML = `
      <div class="signal-card-header">
        <div class="signal-asset-title">
          <span>${escapeHtml(sig.asset_symbol)}</span>
          <span class="signal-dir-badge" style="font-size: 11px;">${arrow}</span>
        </div>
        <span class="confluence-pill">${escapeHtml(sig.strategy_name || 'Confluence VIP')}</span>
      </div>

      <div class="signal-meta-row">
        <div class="signal-meta-item">
          <span class="signal-meta-label">Strike</span>
          <span class="signal-meta-val">${sig.entry_price}</span>
        </div>
        <div class="signal-meta-item">
          <span class="signal-meta-label">Payout</span>
          <span class="signal-meta-val" style="color: var(--emerald);">${sig.live_payout != null ? sig.live_payout + '%' : '85%'}</span>
        </div>
        <div class="signal-meta-item">
          <span class="signal-meta-label">Score</span>
          <span class="signal-meta-val" style="color: var(--amber);">${sig.confidence || 92}%</span>
        </div>
      </div>

      <div class="signal-timer-bar">
        <div class="signal-timer-progress" id="split-progress-${sig.id}" style="width: 100%;"></div>
      </div>

      <div class="signal-footer-row">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span>Expiry: ${sig.duration_minutes || 2}m</span>
          ${pipBadgeHtml}
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${radialHtml}
          ${outcomeBadgeHtml}
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}
window.syncSplitSignalsFeed = syncSplitSignalsFeed;

function updateActiveCountdowns() {
  const now = Math.floor(Date.now() / 1000);

  // Decrement pre-signal countdown timers
  if (AppState.preSignals && AppState.preSignals.length > 0) {
    for (let i = AppState.preSignals.length - 1; i >= 0; i--) {
      const pre = AppState.preSignals[i];
      pre.remaining_seconds = Math.max(0, (pre.remaining_seconds || 15) - 1);
      const symSlug = pre.symbol.replace(/[^a-zA-Z0-9]/g, '_');
      const timerEl = document.getElementById(`pre-timer-${symSlug}`);
      if (timerEl) {
        timerEl.textContent = `⏳ ${pre.remaining_seconds}s`;
      }
      if (pre.remaining_seconds <= 0) {
        AppState.preSignals.splice(i, 1);
        const bEl = document.getElementById(`pre-banner-${symSlug}`);
        if (bEl) bEl.remove();
      }
    }
  }

  AppState.signals.forEach(sig => {
    if (sig.status === 'WIN' || sig.status === 'LOSS' || sig.status === 'DRAW') return;

    const durationSec = (sig.duration_minutes || 2) * 60;
    const createdAtSec = Math.floor(new Date(sig.created_at || Date.now()).getTime() / 1000);
    const elapsed = now - createdAtSec;
    const remaining = Math.max(0, durationSec - elapsed);

    const timerEl = document.getElementById(`timer-${sig.id}`);
    const splitTimerEl = document.getElementById(`split-timer-${sig.id}`);
    const progressEl = document.getElementById(`progress-${sig.id}`);
    const splitProgressEl = document.getElementById(`split-progress-${sig.id}`);

    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    const timeText = remaining > 0 ? `⏳ ${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : '⏳ Evaluating...';

    if (timerEl) timerEl.textContent = timeText;
    if (splitTimerEl) splitTimerEl.textContent = timeText;

    const pct = Math.max(0, Math.min(100, (remaining / durationSec) * 100));
    if (progressEl) progressEl.style.width = `${pct}%`;
    if (splitProgressEl) splitProgressEl.style.width = `${pct}%`;

    // Radial timer ring (circumference = 87.96)
    const circumference = 87.96;
    const frac = Math.max(0, Math.min(1, remaining / durationSec));
    const offset = circumference * (1 - frac);
    const ringEl = document.getElementById(`radial-ring-${sig.id}`);
    const ringTextEl = document.getElementById(`radial-text-${sig.id}`);
    const splitRingEl = document.getElementById(`split-radial-ring-${sig.id}`);
    const splitRingTextEl = document.getElementById(`split-radial-text-${sig.id}`);

    const shortLabel = remaining >= 60 ? `${Math.floor(remaining / 60)}m` : `${remaining}s`;

    if (ringEl) ringEl.style.strokeDashoffset = offset;
    if (splitRingEl) splitRingEl.style.strokeDashoffset = offset;
    if (ringTextEl) ringTextEl.textContent = remaining > 0 ? shortLabel : 'EXP';
    if (splitRingTextEl) splitRingTextEl.textContent = remaining > 0 ? shortLabel : 'EXP';

    // Live Pip Distance
    const curPrice = AppState.prices[sig.asset_symbol];
    if (curPrice != null && sig.entry_price != null) {
      const isCall = (sig.direction || '').toUpperCase() === 'CALL';
      const diff = curPrice - sig.entry_price;
      const isHighOrJpy = sig.asset_symbol.includes('JPY') || curPrice > 20;
      const mult = isHighOrJpy ? 100 : 10000;
      const signedPips = isCall ? (diff * mult) : (-diff * mult);

      let pipBadgeClass = 'pip-badge pip-atm';
      let pipBadgeText = '● 0.0 pips ATM ⚪';
      if (signedPips > 0.05) {
        pipBadgeClass = 'pip-badge pip-itm';
        pipBadgeText = `▲ +${signedPips.toFixed(1)} pips ITM 🟢`;
      } else if (signedPips < -0.05) {
        pipBadgeClass = 'pip-badge pip-otm';
        pipBadgeText = `▼ ${signedPips.toFixed(1)} pips OTM 🔴`;
      }

      const pipEl = document.getElementById(`pip-track-${sig.id}`);
      const splitPipEl = document.getElementById(`split-pip-track-${sig.id}`);
      if (pipEl) {
        pipEl.className = pipBadgeClass;
        pipEl.textContent = pipBadgeText;
      }
      if (splitPipEl) {
        splitPipEl.className = pipBadgeClass;
        splitPipEl.textContent = pipBadgeText;
      }
    }
  });
}

// ============================================================================
// Strategy Lab & Visual Rule Studio
// ============================================================================
function renderStrategyList() {
  const container = document.getElementById('strategy-list-container');
  if (!container) return;
  container.innerHTML = '';

  if (AppState.strategies.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 28px 16px; color: var(--text-dim); font-size: 13px;">
        <div style="font-size: 28px; margin-bottom: 8px;">🎯</div>
        <p style="margin-bottom: 12px; color: var(--text-muted);">No strategies configured yet.</p>
        <button type="button" class="btn-primary" onclick="createNewStrategy()" style="font-size: 12px; padding: 6px 14px; margin: 0 auto; display: inline-flex;">
          <span>+</span> Create First Strategy
        </button>
      </div>
    `;
    resetStrategyForm();
    return;
  }

  AppState.strategies.forEach(s => {
    const card = document.createElement('div');
    card.id = `strat-card-${s.id}`;
    card.className = `strategy-card ${AppState.selectedStrategyId === s.id ? 'active' : ''}`;
    card.onclick = () => selectStrategy(s.id);

    const rawAssets = Array.isArray(s.assets) ? s.assets : ['ALL_MARKETS'];
    let assetBadgeHtml = '<span class="asset-scope-tag">🌐 All Markets</span>';
    if (rawAssets.includes('ALL_MARKETS') || rawAssets.length === 0) {
      assetBadgeHtml = '<span class="asset-scope-tag">🌐 All Markets</span>';
    } else if (rawAssets.includes('ALL_OTC')) {
      assetBadgeHtml = '<span class="asset-scope-tag scope-otc">🌙 OTC Only</span>';
    } else if (rawAssets.includes('ALL_REAL')) {
      assetBadgeHtml = '<span class="asset-scope-tag scope-real">🏛️ Real Forex</span>';
    } else {
      const pairSummary = rawAssets.slice(0, 2).map(p => p.replace(' (OTC)', '')).join(', ') + (rawAssets.length > 2 ? ` +${rawAssets.length - 2}` : '');
      assetBadgeHtml = `<span class="asset-scope-tag scope-custom" title="Assigned Pairs: ${escapeHtml(rawAssets.join(', '))}">🎯 ${escapeHtml(pairSummary)}</span>`;
    }

    card.innerHTML = `
      <div class="strategy-card-top">
        <strong class="strategy-card-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</strong>
        <div class="strategy-card-controls">
          <button type="button" class="btn-delete-strat-icon" title="Delete Strategy" onclick="event.stopPropagation(); deleteStrategy('${s.id}')">🗑️</button>
          <label class="switch" onclick="event.stopPropagation()">
            <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleStrategy('${s.id}', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
      </div>
      <div class="strategy-card-badges">
        ${assetBadgeHtml}
        <span class="strat-pill-tf">⏱️ ${s.timeframe || '1M'} · ${s.expiry_minutes || 2}m</span>
        <span class="strat-pill-meta">Dir: <b style="color: var(--cyan-bright);">${s.direction || 'BOTH'}</b></span>
        <span class="strat-pill-meta">Min <b>${s.min_payout || 85}%</b></span>
      </div>
    `;
    container.appendChild(card);
  });
}

function setAssetScopePreset(scope) {
  AppState.activeAssetScope = scope;
  const parent = document.getElementById('strat-asset-pills');
  if (parent) {
    parent.querySelectorAll('.pill-btn').forEach(b => {
      if (b.dataset.scope === scope) b.classList.add('active');
      else b.classList.remove('active');
    });
  }
  const customBox = document.getElementById('strat-custom-assets-box');
  if (customBox) {
    customBox.style.display = (scope === 'CUSTOM') ? 'block' : 'none';
  }
  updateAssetScopeCountBadge();
}
window.setAssetScopePreset = setAssetScopePreset;

function updateAssetScopeCountBadge() {
  const badge = document.getElementById('strat-asset-count-badge');
  if (!badge) return;
  if (AppState.activeAssetScope === 'ALL_MARKETS') {
    badge.textContent = 'All Markets Active';
    badge.style.color = 'var(--cyan-bright)';
    badge.style.borderColor = 'rgba(0, 240, 255, 0.25)';
  } else if (AppState.activeAssetScope === 'ALL_OTC') {
    badge.textContent = 'All OTC (24/7) Active';
    badge.style.color = '#c084fc';
    badge.style.borderColor = 'rgba(168, 85, 247, 0.3)';
  } else if (AppState.activeAssetScope === 'ALL_REAL') {
    badge.textContent = 'All Real Forex Active';
    badge.style.color = '#4ade80';
    badge.style.borderColor = 'rgba(34, 197, 94, 0.3)';
  } else {
    const count = AppState.selectedStrategyAssets.size;
    badge.textContent = `${count} Currenc${count === 1 ? 'y' : 'ies'} Selected`;
    badge.style.color = count > 0 ? 'var(--cyan-bright)' : 'var(--rose)';
    badge.style.borderColor = count > 0 ? 'rgba(0, 240, 255, 0.25)' : 'rgba(244, 63, 94, 0.4)';
  }
}

function renderAssetPicker(selectedAssets = []) {
  AppState.selectedStrategyAssets = new Set(selectedAssets || []);
  const grid = document.getElementById('strat-asset-chip-grid');
  if (!grid) return;
  grid.innerHTML = '';

  const all = AppState.allAssets && AppState.allAssets.length > 0 ? AppState.allAssets : [
    { symbol: 'EUR/USD (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'GBP/USD (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'USD/JPY (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'AUD/USD (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'USD/INR (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'EUR/GBP (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'USD/CAD (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'EUR/JPY (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'GBP/JPY (OTC)', is_otc: true, category: 'currencies' },
    { symbol: 'EUR/USD', is_otc: false, category: 'currencies' },
    { symbol: 'GBP/USD', is_otc: false, category: 'currencies' },
    { symbol: 'USD/JPY', is_otc: false, category: 'currencies' }
  ];

  all.forEach(asset => {
    const sym = asset.symbol;
    const isSel = AppState.selectedStrategyAssets.has(sym);
    const chip = document.createElement('div');
    chip.className = `asset-chip ${isSel ? 'selected' : ''}`;
    chip.dataset.symbol = sym;
    chip.onclick = () => toggleAssetChip(sym);
    const icon = getAssetIcon(sym, asset.category);
    chip.innerHTML = `
      <span style="display: flex; align-items: center; gap: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        <span>${icon}</span>
        <span style="font-weight: 600;">${escapeHtml(sym)}</span>
      </span>
      <span class="chip-check">✓</span>
    `;
    grid.appendChild(chip);
  });

  updateAssetScopeCountBadge();
}

function toggleAssetChip(symbol) {
  if (AppState.selectedStrategyAssets.has(symbol)) {
    AppState.selectedStrategyAssets.delete(symbol);
  } else {
    AppState.selectedStrategyAssets.add(symbol);
  }
  const grid = document.getElementById('strat-asset-chip-grid');
  if (grid) {
    const chip = grid.querySelector(`[data-symbol="${symbol.replace(/"/g, '\\"')}"]`);
    if (chip) {
      if (AppState.selectedStrategyAssets.has(symbol)) {
        chip.classList.add('selected');
      } else {
        chip.classList.remove('selected');
      }
    }
  }
  updateAssetScopeCountBadge();
}
window.toggleAssetChip = toggleAssetChip;

function filterAssetChips(query) {
  const q = (query || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '');
  const grid = document.getElementById('strat-asset-chip-grid');
  if (!grid) return;
  grid.querySelectorAll('.asset-chip').forEach(chip => {
    const sym = (chip.dataset.symbol || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!q || sym.includes(q)) {
      chip.style.display = 'flex';
    } else {
      chip.style.display = 'none';
    }
  });
}
window.filterAssetChips = filterAssetChips;

function clearAssetFilter() {
  const input = document.getElementById('strat-asset-search');
  if (input) input.value = '';
  filterAssetChips('');
}
window.clearAssetFilter = clearAssetFilter;

function selectAssetPresetGroup(group) {
  const all = AppState.allAssets || [];
  if (group === 'OTC') {
    all.forEach(a => {
      if (a.is_otc || a.symbol.includes('(OTC)')) AppState.selectedStrategyAssets.add(a.symbol);
    });
  } else if (group === 'REAL') {
    all.forEach(a => {
      if (!a.is_otc && !a.symbol.includes('(OTC)')) AppState.selectedStrategyAssets.add(a.symbol);
    });
  } else if (group === 'TOP') {
    const topPairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'EUR/USD (OTC)', 'GBP/USD (OTC)', 'USD/JPY (OTC)', 'USD/INR (OTC)', 'AUD/CAD (OTC)'];
    all.forEach(a => {
      if (topPairs.some(p => a.symbol.includes(p) || p.includes(a.symbol))) {
        AppState.selectedStrategyAssets.add(a.symbol);
      }
    });
  } else if (group === 'CLEAR') {
    AppState.selectedStrategyAssets.clear();
  }

  const grid = document.getElementById('strat-asset-chip-grid');
  if (grid) {
    grid.querySelectorAll('.asset-chip').forEach(chip => {
      const sym = chip.dataset.symbol;
      if (AppState.selectedStrategyAssets.has(sym)) {
        chip.classList.add('selected');
      } else {
        chip.classList.remove('selected');
      }
    });
  }
  updateAssetScopeCountBadge();
}
window.selectAssetPresetGroup = selectAssetPresetGroup;

function selectStrategy(id) {
  AppState.selectedStrategyId = id;
  renderStrategyList();
  const strat = AppState.strategies.find(s => s.id === id);
  if (!strat) return;

  const titleEl = document.getElementById('strat-editor-title');
  if (titleEl) titleEl.textContent = `Edit Strategy: ${strat.name}`;

  document.getElementById('strat-id').value = strat.id;
  document.getElementById('strat-name').value = strat.name;
  document.getElementById('strat-duration').value = strat.expiry_minutes || 2;
  document.getElementById('strat-min-payout').value = strat.min_payout || 85;

  AppState.activeDirection = strat.direction || 'BOTH';
  AppState.activeTimeframe = strat.timeframe || '1M';
  updatePillSelection('strat-direction-pills', AppState.activeDirection);
  updatePillSelection('strat-tf-pills', AppState.activeTimeframe);

  // Asset Scope & Currency Assignment
  const rawAssets = Array.isArray(strat.assets) ? strat.assets : ['ALL_MARKETS'];
  if (rawAssets.includes('ALL_MARKETS') || rawAssets.length === 0) {
    setAssetScopePreset('ALL_MARKETS');
    renderAssetPicker([]);
  } else if (rawAssets.includes('ALL_OTC')) {
    setAssetScopePreset('ALL_OTC');
    renderAssetPicker([]);
  } else if (rawAssets.includes('ALL_REAL')) {
    setAssetScopePreset('ALL_REAL');
    renderAssetPicker([]);
  } else {
    setAssetScopePreset('CUSTOM');
    renderAssetPicker(rawAssets);
  }

  const filters = strat.filters || {};
  const pa = filters.price_action || {};
  const ca = filters.candle_anatomy || {};
  const trend = filters.trend || {};
  const inds = filters.indicators || [];

  const solidEl = document.getElementById('rule-solid-body');
  if (solidEl) solidEl.checked = (ca.min_body_ratio !== undefined ? ca.min_body_ratio >= 0.50 : true);

  const engulfingEl = document.getElementById('rule-engulfing');
  if (engulfingEl) engulfingEl.checked = pa.require_engulfing ?? false;

  const wickEl = document.getElementById('rule-wick');
  if (wickEl) wickEl.checked = (ca.max_opposing_wick !== undefined ? ca.max_opposing_wick <= 0.35 : true);

  const trendEl = document.getElementById('rule-trend');
  if (trendEl) trendEl.checked = trend.enabled ?? false;

  const rsiEl = document.getElementById('rule-rsi');
  if (rsiEl) rsiEl.checked = Array.isArray(inds) && inds.some(i => i.indicator === 'RSI');

  const delBtn = document.getElementById('btn-delete-strat');
  if (delBtn) delBtn.style.display = 'inline-block';
}

async function createNewStrategy() {
  const newId = 'strat_' + Date.now();
  const nextNum = AppState.strategies.length + 1;
  const newName = `Custom Strategy #${nextNum}`;

  const newStrat = {
    id: newId,
    name: newName,
    direction: 'BOTH',
    timeframe: '1M',
    expiry_minutes: 2,
    min_payout: 85.0,
    enabled: true,
    assets: ['ALL_MARKETS'],
    filters: {
      trend: { enabled: false, mtf_timeframe: '5M', ema_period: 20, require_alignment: true },
      candle_anatomy: { min_body_ratio: 0.55, max_opposing_wick: 0.25, filter_preceding_doji: true, filter_spike_multiplier: 3.0 },
      indicators: [],
      price_action: { require_engulfing: false, require_sr_breakout: false, min_sr_clearance_pct: 0.1 },
      smc: { fvg_enabled: false, liquidity_sweep_enabled: false, bos_enabled: false, order_block_enabled: false }
    }
  };

  // Add immediately to local state and UI at top of list
  AppState.strategies.unshift(newStrat);
  AppState.selectedStrategyId = newId;
  renderStrategyList();
  selectStrategy(newId);

  // Visual feedback: animate new card & editor
  const newCard = document.getElementById(`strat-card-${newId}`);
  if (newCard) {
    newCard.classList.add('pulse-highlight');
    setTimeout(() => newCard.classList.remove('pulse-highlight'), 1200);
  }
  const formCard = document.getElementById('strategy-form')?.closest('.panel-card');
  if (formCard) {
    formCard.classList.add('pulse-highlight');
    setTimeout(() => formCard.classList.remove('pulse-highlight'), 1200);
  }

  // Update active count
  const activeCountEl = document.getElementById('stat-active-strats');
  if (activeCountEl) {
    activeCountEl.textContent = AppState.strategies.filter(s => s.enabled).length;
  }

  // Focus and select the name input so user can edit right away
  const nameInput = document.getElementById('strat-name');
  if (nameInput) {
    nameInput.focus();
    nameInput.select();
  }

  // Persist to backend
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_strategy) {
    try {
      const saved = await window.pywebview.api.save_strategy(newStrat);
      if (saved && saved.id) {
        const idx = AppState.strategies.findIndex(s => s.id === newId);
        if (idx !== -1) AppState.strategies[idx] = saved;
      }
    } catch (err) {
      console.error('[STRATEGY] Backend error saving new strategy:', err);
    }
  }

  showToast(`Created "${newName}". Edit rules and click Save.`, 'success');
}
window.createNewStrategy = createNewStrategy;

function resetStrategyForm() {
  document.getElementById('strat-id').value = '';
  document.getElementById('strat-name').value = '';
  document.getElementById('strat-duration').value = '2';
  document.getElementById('strat-min-payout').value = '85';
  AppState.activeDirection = 'BOTH';
  AppState.activeTimeframe = '1M';
  updatePillSelection('strat-direction-pills', 'BOTH');
  updatePillSelection('strat-tf-pills', '1M');

  setAssetScopePreset('ALL_MARKETS');
  renderAssetPicker([]);

  const solidEl = document.getElementById('rule-solid-body');
  if (solidEl) solidEl.checked = true;
  const engulfingEl = document.getElementById('rule-engulfing');
  if (engulfingEl) engulfingEl.checked = false;
  const wickEl = document.getElementById('rule-wick');
  if (wickEl) wickEl.checked = true;
  const trendEl = document.getElementById('rule-trend');
  if (trendEl) trendEl.checked = false;
  const rsiEl = document.getElementById('rule-rsi');
  if (rsiEl) rsiEl.checked = false;

  const titleEl = document.getElementById('strat-editor-title');
  if (titleEl) titleEl.textContent = 'Create New Strategy';

  const delBtn = document.getElementById('btn-delete-strat');
  if (delBtn) delBtn.style.display = 'none';
}
window.resetStrategyForm = resetStrategyForm;

function selectPill(btn, type) {
  const parent = btn.parentElement;
  parent.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (type === 'direction') AppState.activeDirection = btn.dataset.val;
  if (type === 'timeframe') AppState.activeTimeframe = btn.dataset.val;
}
window.selectPill = selectPill;

function updatePillSelection(parentId, val) {
  const parent = document.getElementById(parentId);
  if (!parent) return;
  parent.querySelectorAll('.pill-btn').forEach(b => {
    if (b.dataset.val === val) b.classList.add('active');
    else b.classList.remove('active');
  });
}

async function handleSaveStrategy(e) {
  if (e && e.preventDefault) e.preventDefault();

  const stratId = document.getElementById('strat-id').value || ('strat_' + Date.now());
  const stratName = document.getElementById('strat-name').value.trim() || 'Custom Strategy';
  const duration = parseInt(document.getElementById('strat-duration').value, 10) || 2;
  const minPayout = parseFloat(document.getElementById('strat-min-payout').value) || 85;

  const ruleSolid = document.getElementById('rule-solid-body')?.checked ?? true;
  const ruleEngulfing = document.getElementById('rule-engulfing')?.checked ?? false;
  const ruleWick = document.getElementById('rule-wick')?.checked ?? true;
  const ruleTrend = document.getElementById('rule-trend')?.checked ?? false;
  const ruleRsi = document.getElementById('rule-rsi')?.checked ?? false;

  const existingStrat = AppState.strategies.find(s => s.id === stratId);
  const baseFilters = (existingStrat && existingStrat.filters) ? JSON.parse(JSON.stringify(existingStrat.filters)) : {};

  // Resolve assigned currencies according to active scope preset
  let savedAssets = ['ALL_MARKETS'];
  if (AppState.activeAssetScope === 'ALL_MARKETS') {
    savedAssets = ['ALL_MARKETS'];
  } else if (AppState.activeAssetScope === 'ALL_OTC') {
    savedAssets = ['ALL_OTC'];
  } else if (AppState.activeAssetScope === 'ALL_REAL') {
    savedAssets = ['ALL_REAL'];
  } else {
    savedAssets = Array.from(AppState.selectedStrategyAssets);
    if (savedAssets.length === 0) {
      savedAssets = ['ALL_MARKETS'];
      showToast('No specific currencies chosen. Defaulted to All Markets.', 'info');
      setAssetScopePreset('ALL_MARKETS');
    }
  }

  const strat = {
    id: stratId,
    name: stratName,
    direction: AppState.activeDirection || 'BOTH',
    timeframe: AppState.activeTimeframe || '1M',
    expiry_minutes: duration,
    min_payout: minPayout,
    enabled: existingStrat ? existingStrat.enabled : true,
    assets: savedAssets,
    filters: {
      trend: {
        enabled: ruleTrend,
        mtf_timeframe: baseFilters.trend?.mtf_timeframe || '5M',
        ema_period: baseFilters.trend?.ema_period || 20,
        require_alignment: true
      },
      candle_anatomy: {
        min_body_ratio: ruleSolid ? 0.55 : 0.40,
        max_opposing_wick: ruleWick ? 0.25 : 0.45,
        filter_preceding_doji: true,
        filter_spike_multiplier: 3.0
      },
      indicators: ruleRsi ? [{ indicator: 'RSI', period: 14, condition: 'BETWEEN', min_val: 30, max_val: 70 }] : [],
      price_action: {
        require_engulfing: ruleEngulfing,
        require_sr_breakout: baseFilters.price_action?.require_sr_breakout || false,
        min_sr_clearance_pct: baseFilters.price_action?.min_sr_clearance_pct || 0.1
      },
      smc: baseFilters.smc || {
        fvg_enabled: false,
        liquidity_sweep_enabled: false,
        bos_enabled: false,
        order_block_enabled: false
      }
    }
  };

  const idx = AppState.strategies.findIndex(s => s.id === strat.id);
  if (idx !== -1) {
    AppState.strategies[idx] = strat;
  } else {
    AppState.strategies.unshift(strat);
  }

  AppState.selectedStrategyId = strat.id;
  document.getElementById('strat-id').value = strat.id;
  renderStrategyList();
  selectStrategy(strat.id);

  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_strategy) {
    try {
      const saved = await window.pywebview.api.save_strategy(strat);
      if (saved && saved.id) {
        const i = AppState.strategies.findIndex(s => s.id === strat.id);
        if (i !== -1) AppState.strategies[i] = saved;
      }
    } catch (err) {
      console.error('[STRATEGY] Error saving strategy to backend:', err);
      showToast('Error saving to backend disk, saved in-memory', 'error');
      return;
    }
  }

  const activeCountEl = document.getElementById('stat-active-strats');
  if (activeCountEl) {
    activeCountEl.textContent = AppState.strategies.filter(s => s.enabled).length;
  }

  showToast(`Strategy "${strat.name}" saved successfully!`, 'success');
}
window.handleSaveStrategy = handleSaveStrategy;

async function deleteStrategy(id) {
  const strat = AppState.strategies.find(s => s.id === id);
  const name = strat ? strat.name : 'this strategy';

  AppState.strategies = AppState.strategies.filter(s => s.id !== id);
  if (AppState.selectedStrategyId === id) {
    AppState.selectedStrategyId = AppState.strategies.length > 0 ? AppState.strategies[0].id : null;
  }

  renderStrategyList();
  if (AppState.selectedStrategyId) {
    selectStrategy(AppState.selectedStrategyId);
  } else {
    resetStrategyForm();
  }

  const activeCountEl = document.getElementById('stat-active-strats');
  if (activeCountEl) {
    activeCountEl.textContent = AppState.strategies.filter(s => s.enabled).length;
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.delete_strategy) {
    try {
      await window.pywebview.api.delete_strategy(id);
    } catch (err) {
      console.error('[STRATEGY] Error deleting strategy:', err);
    }
  }

  showToast(`Deleted strategy "${name}".`, 'info');
}
window.deleteStrategy = deleteStrategy;

function handleDeleteSelectedStrategy() {
  if (AppState.selectedStrategyId) {
    deleteStrategy(AppState.selectedStrategyId);
  }
}
window.handleDeleteSelectedStrategy = handleDeleteSelectedStrategy;

function toggleStrategy(id, isEnabled) {
  const strat = AppState.strategies.find(s => s.id === id);
  if (strat) {
    strat.enabled = isEnabled;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_strategy) {
      window.pywebview.api.toggle_strategy(id, isEnabled);
    }
    const activeCountEl = document.getElementById('stat-active-strats');
    if (activeCountEl) {
      activeCountEl.textContent = AppState.strategies.filter(s => s.enabled).length;
    }
  }
}
window.toggleStrategy = toggleStrategy;

function runStrategyBacktest() {
  const box = document.getElementById('backtest-result-box');
  const grid = document.getElementById('backtest-metrics-grid');
  if (!box || !grid) return;

  box.style.display = 'block';
  grid.innerHTML = '<div style="grid-column: 1/-1; color: var(--cyan-bright); padding: 10px 0;">Running backtest across in-memory candle store...</div>';

  if (window.pywebview && window.pywebview.api && window.pywebview.api.run_backtest) {
    const stratId = AppState.selectedStrategyId || (AppState.strategies[0] ? AppState.strategies[0].id : null);
    window.pywebview.api.run_backtest(stratId).then(res => {
      if (!res || res.error) {
        const errMsg = (res && res.error) ? res.error : 'Insufficient candle history to complete backtest. Let scanner run for ~15 minutes.';
        grid.innerHTML = `<div style="grid-column: 1/-1; color: var(--rose); padding: 8px 0;">${escapeHtml(errMsg)}</div>`;
        return;
      }
      grid.innerHTML = `
        <div style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px;">
          <div style="color: var(--text-dim); font-size: 10px;">TOTAL TRADES</div>
          <div style="font-size: 15px; font-weight: 800; color: #fff;">${res.total_trades || 0}</div>
        </div>
        <div style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px;">
          <div style="color: var(--text-dim); font-size: 10px;">WIN RATE</div>
          <div style="font-size: 15px; font-weight: 800; color: var(--emerald);">${res.win_rate || 0}%</div>
        </div>
        <div style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px;">
          <div style="color: var(--text-dim); font-size: 10px;">NET PROFIT</div>
          <div style="font-size: 15px; font-weight: 800; color: ${res.net_profit >= 0 ? 'var(--emerald)' : 'var(--rose)'};">${res.net_profit || 0}%</div>
        </div>
      `;
    });
  }
}
window.runStrategyBacktest = runStrategyBacktest;

// ============================================================================
// Telegram & Webhook Dispatch Relay
// ============================================================================
function handleSaveTelegram(e) {
  e.preventDefault();
  const token = document.getElementById('tg-token').value.trim();
  const chatId = document.getElementById('tg-chat-id').value.trim();
  const sendCharts = document.getElementById('tg-send-charts').checked;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_telegram_config) {
    window.pywebview.api.save_telegram_config(token, chatId, sendCharts).then(res => {
      showToast('Telegram VIP credentials saved securely.', 'success');
    });
  }
}
window.handleSaveTelegram = handleSaveTelegram;

function testTelegramBroadcast() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.test_telegram) {
    window.pywebview.api.test_telegram().then(res => {
      showToast(res ? 'VIP Test Alert dispatched to Telegram!' : 'Failed to send. Check bot token and chat ID.', res ? 'success' : 'error');
    });
  }
}
window.testTelegramBroadcast = testTelegramBroadcast;

function copyWebhookUrl() {
  const el = document.getElementById('webhook-url');
  if (el) {
    navigator.clipboard.writeText(el.value);
    showToast('Copied webhook endpoint URL!', 'success');
  }
}
window.copyWebhookUrl = copyWebhookUrl;

function copyWebhookJson() {
  const el = document.getElementById('webhook-json');
  if (el) {
    navigator.clipboard.writeText(el.value);
    showToast('Copied TradingView Alert payload JSON!', 'success');
  }
}
window.copyWebhookJson = copyWebhookJson;

// ============================================================================
// History & PnL View
// ============================================================================
function filterHistory(btn) {
  const parent = document.getElementById('history-filter-pills');
  if (parent) parent.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  AppState.historyFilter = btn.dataset.val;
  renderHistoryTable();
}
window.filterHistory = filterHistory;

function filterHistorySearch(val) {
  AppState.historySearchQuery = (val || '').trim().toLowerCase();
  renderHistoryTable();
}
window.filterHistorySearch = filterHistorySearch;

function renderHistoryTable() {
  const tbody = document.getElementById('history-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const filter = AppState.historyFilter;
  const q = AppState.historySearchQuery;

  const rows = AppState.signals.filter(s => {
    if (filter !== 'ALL' && s.status !== filter) return false;
    if (q && !s.asset_symbol.toLowerCase().includes(q)) return false;
    return true;
  });

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 24px; color: var(--text-dim);">No historical signals match filter.</td></tr>';
    renderEquityCurve();
    return;
  }

  rows.forEach(s => {
    const isWin = s.status === 'WIN';
    const isLoss = s.status === 'LOSS';
    const isDraw = s.status === 'DRAW';
    const isActive = !s.status || s.status === 'ACTIVE';
    const badgeClass = isWin ? 'payout-high' : (isLoss ? 'payout-low' : (isDraw ? 'payout-mid' : 'payout-mid'));
    const isCall = (s.direction || '').toUpperCase() === 'CALL';
    const dirClass = isCall ? 'dir-call' : 'dir-put';
    const dirArrow = isCall ? '▲' : '▼';

    let timeStr = '-';
    if (s.created_at) {
      try {
        const d = new Date(s.created_at);
        if (!isNaN(d.getTime())) {
          timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }
      } catch(e) {}
    }

    let exitDisplay = '-';
    if (s.exit_price != null && s.exit_price > 0) {
      exitDisplay = formatPrice(s.asset_symbol, s.exit_price);
    } else if (isActive && AppState.prices && AppState.prices[s.asset_symbol]) {
      const cur = AppState.prices[s.asset_symbol];
      exitDisplay = `<span style="color: var(--cyan-bright);">${formatPrice(s.asset_symbol, cur)} <span style="font-size: 8px;">●</span></span>`;
    }

    const entryDisplay = s.entry_price != null ? formatPrice(s.asset_symbol, s.entry_price) : '-';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-dim);">${timeStr}</td>
      <td style="font-weight: 700; color: #fff;">${escapeHtml(s.asset_symbol || '')}</td>
      <td>
        <span class="history-strat-tag" title="${escapeHtml(s.strategy_name || 'Confluence')}">
          ${escapeHtml(s.strategy_name || 'Confluence')}
        </span>
      </td>
      <td style="text-align: center;">
        <span class="history-dir-badge ${dirClass}">${dirArrow} ${s.direction || 'CALL'}</span>
      </td>
      <td style="font-family: var(--font-mono);">${entryDisplay}</td>
      <td style="font-family: var(--font-mono);">${exitDisplay}</td>
      <td style="font-family: var(--font-mono); text-align: right; color: var(--emerald); font-weight: 700;">${s.live_payout ? s.live_payout + '%' : '-'}</td>
      <td style="text-align: center;"><span class="payout-badge ${badgeClass}" style="${isActive ? 'animation: pulse-active 1.5s infinite;' : ''}">${s.status || 'ACTIVE'}</span></td>
    `;
    tbody.appendChild(tr);
  });

  renderEquityCurve();
}

// Live Real-Time Auto-Refresh for History & PnL view
setInterval(() => {
  if (AppState.activeView === 'history') {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_signals_history) {
      window.pywebview.api.get_signals_history(100).then(sigs => {
        if (Array.isArray(sigs) && sigs.length > 0) {
          AppState.signals = sigs;
          renderHistoryTable();
        }
      }).catch(() => {});
    } else {
      renderHistoryTable();
    }
  }
}, 2000);

function renderEquityCurve() {
  const canvas = document.getElementById('equityCurveCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(300, rect.width || 700);
  const height = Math.max(120, rect.height || 180);

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, width, height);

  const resolved = AppState.signals
    .filter(s => s.status === 'WIN' || s.status === 'LOSS' || s.status === 'DRAW')
    .slice()
    .reverse();

  let curStreak = 0;
  let maxStreak = 0;
  let runningBal = 1000;
  const points = [{ val: runningBal, status: 'INIT' }];

  resolved.forEach(s => {
    const payoutPct = (s.live_payout || 85) / 100;
    if (s.status === 'WIN') {
      runningBal += 10 * payoutPct;
      curStreak = curStreak > 0 ? curStreak + 1 : 1;
      if (curStreak > maxStreak) maxStreak = curStreak;
    } else if (s.status === 'LOSS') {
      runningBal -= 10;
      curStreak = curStreak < 0 ? curStreak - 1 : -1;
    }
    points.push({ val: runningBal, status: s.status });
  });

  const bestEl = document.getElementById('journal-best-streak') || document.getElementById('history-best-streak');
  const curEl = document.getElementById('journal-current-streak') || document.getElementById('history-cur-streak');
  const retEl = document.getElementById('journal-net-return');

  if (bestEl) bestEl.textContent = `🏆 Best Streak: ${maxStreak} W`;
  if (curEl) curEl.textContent = curStreak >= 0 ? `🔥 Current Streak: ${curStreak} W` : `❄️ Current Streak: ${Math.abs(curStreak)} L`;
  if (retEl) {
    const netReturnPct = ((runningBal - 1000) / 10).toFixed(1);
    const sign = netReturnPct >= 0 ? '+' : '';
    retEl.textContent = `💰 Return: ${sign}${netReturnPct}%`;
    retEl.style.color = netReturnPct >= 0 ? 'var(--emerald)' : 'var(--rose)';
  }

  if (points.length < 2) {
    ctx.fillStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Accumulating trade outcomes to plot equity trajectory...', width / 2, height / 2);
    return;
  }

  let minVal = Infinity, maxVal = -Infinity;
  points.forEach(p => {
    if (p.val < minVal) minVal = p.val;
    if (p.val > maxVal) maxVal = p.val;
  });

  const pad = Math.max(5, (maxVal - minVal) * 0.15);
  minVal -= pad;
  maxVal += pad;
  const range = maxVal - minVal || 1;

  const padX = 46;
  const padY = 22;
  const drawW = width - padX * 2;
  const drawH = height - padY * 2;

  const getX = (i) => padX + (i / (points.length - 1)) * drawW;
  const getY = (val) => padY + drawH - ((val - minVal) / range) * drawH;

  // Horizontal grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const gy = padY + (drawH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padX, gy);
    ctx.lineTo(width - padX, gy);
    ctx.stroke();

    const gVal = maxVal - (range / 4) * i;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(`$${gVal.toFixed(0)}`, padX - 8, gy);
  }

  // Baseline $1000
  const baseLineY = getY(1000);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(padX, baseLineY);
  ctx.lineTo(width - padX, baseLineY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Smooth curve
  const isProfitable = runningBal >= 1000;
  const strokeColor = isProfitable ? '#00f0ff' : '#f43f5e';
  const fillColorTop = isProfitable ? 'rgba(0, 240, 255, 0.28)' : 'rgba(244, 63, 94, 0.28)';

  ctx.beginPath();
  ctx.moveTo(getX(0), getY(points[0].val));
  for (let i = 1; i < points.length; i++) {
    const prevX = getX(i - 1);
    const prevY = getY(points[i - 1].val);
    const curX = getX(i);
    const curY = getY(points[i].val);
    const midX = (prevX + curX) / 2;
    ctx.bezierCurveTo(midX, prevY, midX, curY, curX, curY);
  }

  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Gradient fill under curve
  ctx.lineTo(getX(points.length - 1), height - padY);
  ctx.lineTo(getX(0), height - padY);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, padY, 0, height - padY);
  grad.addColorStop(0, fillColorTop);
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw head point dot
  const lastX = getX(points.length - 1);
  const lastY = getY(points[points.length - 1].val);

  ctx.beginPath();
  ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fillStyle = strokeColor;
  ctx.shadowColor = strokeColor;
  ctx.shadowBlur = 10;
  ctx.fill();
  ctx.shadowBlur = 0;

  // Render glassmorphic pill background for equity label to prevent text collision
  const netReturnPct = ((runningBal - 1000) / 10).toFixed(1);
  const sign = netReturnPct >= 0 ? '+' : '';
  const labelText = `$${runningBal.toFixed(1)} (${sign}${netReturnPct}%)`;
  ctx.font = 'bold 11px JetBrains Mono, monospace';
  const textW = ctx.measureText(labelText).width;
  const pillW = textW + 16;
  const pillH = 22;
  const isRightAnchored = lastX > width - pillW - 14;
  const pillX = isRightAnchored ? lastX - pillW - 10 : lastX + 10;
  const pillY = Math.max(padY + 2, Math.min(height - padY - pillH - 2, lastY - pillH / 2));

  ctx.fillStyle = 'rgba(11, 16, 26, 0.88)';
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1;
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(pillX, pillY, pillW, pillH, 4);
  } else {
    ctx.rect(pillX, pillY, pillW, pillH);
  }
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(labelText, pillX + 8, pillY + pillH / 2);
}
window.renderEquityCurve = renderEquityCurve;

function exportHistoryCSV() {
  if (AppState.signals.length === 0) {
    showToast('No signals to export.', 'info');
    return;
  }
  let csv = 'ID,Asset,Direction,Strategy,Strike,Exit,Payout,Status,Time\n';
  AppState.signals.forEach(s => {
    csv += `"${s.id}","${s.asset_symbol}","${s.direction}","${s.strategy_name || ''}","${s.entry_price || ''}","${s.exit_price || ''}","${s.live_payout || ''}","${s.status || ''}","${s.created_at || ''}"\n`;
  });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `TradePulse_History_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}
window.exportHistoryCSV = exportHistoryCSV;

// ============================================================================
// Preferences & Broker Session Management
// ============================================================================
function openLoginModal() {
  switchView('broker');
}
window.openLoginModal = openLoginModal;

function clearBrokerSession() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.clear_broker_session) {
    window.pywebview.api.clear_broker_session().then(() => {
      showToast('Broker session cleared. Opening terminal for sign in...', 'info');
      switchView('broker');
    });
  }
}
window.clearBrokerSession = clearBrokerSession;

function saveCooldownPref(val) {
  const sec = parseInt(val, 10);
  if (isNaN(sec) || sec < 10) return;
  localStorage.setItem('tradepulse_cooldown_pref', sec);
  const statusEl = document.getElementById('pref-cooldown-status');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_global_cooldown) {
    window.pywebview.api.set_global_cooldown(sec).then(res => {
      if (statusEl) {
        statusEl.textContent = `✅ Cooldown updated to ${sec}s across all strategies.`;
        statusEl.style.color = 'var(--emerald)';
        setTimeout(() => {
          if (statusEl) {
            statusEl.textContent = 'Minimum time window between consecutive signals on the same asset.';
            statusEl.style.color = 'var(--text-dim)';
          }
        }, 3000);
      }
    });
  } else if (statusEl) {
    statusEl.textContent = `Saved locally: ${sec}s`;
  }
}
window.saveCooldownPref = saveCooldownPref;

// ============================================================================
// Integrated Quotex Broker Station Layout & Controls
// ============================================================================
let isBrokerExpanded = false;
let lastBrokerPos = { x: -1, y: -1, w: -1, h: -1, vis: null };

function syncBrokerStationLayout(force = false) {
  if (!window.pywebview || !window.pywebview.api) {
    return;
  }

  const isBrokerView = AppState.activeView === 'broker';
  const isSplitMode = AppState.activeView === 'monitor' && AppState.terminalLayout === 'split';

  let x = 0, y = 0, w = 0, h = 0, isVis = false;
  if (isBrokerView) {
    const canvas = document.getElementById('broker-terminal-canvas');
    if (canvas) {
      const rect = canvas.getBoundingClientRect();
      x = Math.round(rect.left);
      y = Math.round(rect.top);
      w = Math.round(rect.width);
      h = Math.round(rect.height);
      isVis = w > 50 && h > 50;
    }
  } else if (isSplitMode) {
    const anchor = document.getElementById('split-broker-anchor');
    if (anchor) {
      const rect = anchor.getBoundingClientRect();
      x = Math.round(rect.left);
      y = Math.round(rect.top);
      w = Math.round(rect.width);
      h = Math.round(rect.height);
      isVis = w > 50 && h > 50;
    }
  }

  // If NOT in broker view and NOT in monitor split mode, GUARANTEE isVis is false
  if (!isBrokerView && !isSplitMode) {
    isVis = false;
    x = 0;
    y = 0;
    w = 0;
    h = 0;
  }

  if (!window.pywebview.api.sync_broker_position) {
    if (window.pywebview.api.set_broker_visible) {
      window.pywebview.api.set_broker_visible(isVis);
    }
    return;
  }

  if (
    !force &&
    lastBrokerPos.x === x &&
    lastBrokerPos.y === y &&
    lastBrokerPos.w === w &&
    lastBrokerPos.h === h &&
    lastBrokerPos.vis === isVis
  ) {
    return;
  }

  lastBrokerPos = { x, y, w, h, vis: isVis };
  try {
    window.pywebview.api.sync_broker_position(x, y, w, h, isVis);
  } catch(e) {}
}

let currentBrokerBase = 'https://qxbroker.com';

function navigateBrokerDomain(domain) {
  currentBrokerBase = domain;
  document.querySelectorAll('[id^="mirror-btn-"]').forEach(btn => btn.classList.remove('active-mirror'));
  if (domain.includes('qx-market')) {
    const b = document.getElementById('mirror-btn-qxmarket');
    if (b) b.classList.add('active-mirror');
  } else if (domain.includes('qxbroker.io')) {
    const b = document.getElementById('mirror-btn-qxbrokerio');
    if (b) b.classList.add('active-mirror');
  } else if (domain.includes('quotex-broker')) {
    const b = document.getElementById('mirror-btn-quotexbroker');
    if (b) b.classList.add('active-mirror');
  } else if (domain.includes('qxbroker.com')) {
    const b = document.getElementById('mirror-btn-qxbroker');
    if (b) b.classList.add('active-mirror');
  }
  const input = document.getElementById('broker-url-input');
  if (input) input.value = currentBrokerBase;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker) {
    window.pywebview.api.navigate_broker(currentBrokerBase + '/en/sign-in');
  }
}
window.navigateBrokerDomain = navigateBrokerDomain;

function navigateCustomUrl() {
  const input = document.getElementById('broker-url-input');
  if (!input) return;
  let url = input.value.trim();
  if (!url) return;
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url;
  }
  try {
    const parsed = new URL(url);
    currentBrokerBase = parsed.origin;
  } catch(e) {}
  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker) {
    window.pywebview.api.navigate_broker(url);
  }
}
window.navigateCustomUrl = navigateCustomUrl;

function refreshBrokerView() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.refresh_broker) {
    window.pywebview.api.refresh_broker();
  }
}
window.refreshBrokerView = refreshBrokerView;

function navigateBrokerSignIn() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker) {
    window.pywebview.api.navigate_broker(currentBrokerBase + '/en/sign-in');
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker_signin) {
    window.pywebview.api.navigate_broker_signin();
  }
}
window.navigateBrokerSignIn = navigateBrokerSignIn;

function navigateBrokerTrade() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker) {
    window.pywebview.api.navigate_broker(currentBrokerBase + '/en/trade');
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate_broker_trade) {
    window.pywebview.api.navigate_broker_trade();
  }
}
window.navigateBrokerTrade = navigateBrokerTrade;

// ============================================================================
// Helpers & State Initializer
// ============================================================================
function initFullState(state) {
  if (!state) return;
  AppState.connected = state.connected;
  AppState.payouts = state.payouts || {};
  AppState.prices = state.prices || {};
  AppState.priceSources = state.price_sources || {};
  AppState.strategies = state.strategies || [];
  AppState.signals = state.signals || [];
  AppState.stats = state.stats || AppState.stats;

  if (state.tool_active !== undefined) {
    updateToolStatusUI(state.tool_active);
  } else if (state.scanning_paused !== undefined) {
    updateToolStatusUI(!state.scanning_paused);
  } else {
    updateToolStatusUI(true);
  }

  if (AppState.activeView === 'strategies') {
    if (!AppState.selectedStrategyId && AppState.strategies.length > 0) {
      selectStrategy(AppState.strategies[0].id);
    } else {
      renderStrategyList();
    }
  }

  window.onBrokerStatus(
    state.connected ? 'connected' : 'disconnected',
    state.status_text,
    state.latency
  );

  const banner = document.getElementById('broker-connect-banner');
  if (banner) {
    banner.style.display = state.connected ? 'none' : 'flex';
  }

  const activeCountEl = document.getElementById('stat-active-strats');
  if (activeCountEl) {
    activeCountEl.textContent = AppState.strategies.filter(s => s.enabled).length;
  }
  const statSigEl = document.getElementById('stat-signals');
  if (statSigEl) statSigEl.textContent = AppState.stats.total_signals || 0;
  const winRateEl = document.getElementById('stat-win-rate');
  if (winRateEl) winRateEl.textContent = `${AppState.stats.win_rate || 0}%`;

  if (state.telegram_token) {
    const tokenInput = document.getElementById('tg-token');
    if (tokenInput && !tokenInput.value) tokenInput.value = state.telegram_token;
  }
  if (state.telegram_chat_id) {
    const chatInput = document.getElementById('tg-chat-id');
    if (chatInput && !chatInput.value) chatInput.value = state.telegram_chat_id;
  }
  if (state.telegram_manager && window.initTelegramManagerState) {
    window.initTelegramManagerState(state.telegram_manager);
  }
  if (state.webhook_endpoint) {
    const hookInput = document.getElementById('webhook-url');
    if (hookInput) hookInput.value = state.webhook_endpoint;
  }
  if (state.global_cooldown) {
    const cdInput = document.getElementById('pref-cooldown');
    if (cdInput && !localStorage.getItem('tradepulse_cooldown_pref')) {
      cdInput.value = state.global_cooldown;
    }
  }

  AppState.allAssets = state.assets || [];
  AppState.precisions = AppState.precisions || {};
  (state.assets || []).forEach(a => {
    if (a.symbol && a.precision !== undefined) {
      AppState.precisions[a.symbol] = a.precision;
    }
  });
  updateQuickPairSelector(AppState.allAssets);
  renderMarketsTable(AppState.allAssets);

  // Initialize Institutional Safeguards & Filters
  if (state.advanced_filters) {
    AppState.advancedFilters = state.advanced_filters;
    if (typeof applyAdvancedFiltersToUI === 'function') {
      applyAdvancedFiltersToUI(state.advanced_filters);
    }
  }
  if (state.risk_metrics) {
    AppState.riskMetrics = state.risk_metrics;
    if (typeof updateRiskMetricsUI === 'function') {
      updateRiskMetricsUI(state.risk_metrics);
    }
  }
  if (state.upcoming_news) {
    AppState.upcomingNews = state.upcoming_news;
    if (typeof renderUpcomingNewsList === 'function') {
      renderUpcomingNewsList(state.upcoming_news);
    }
  }
  if (typeof updateSafeguardsStrip === 'function') {
    updateSafeguardsStrip();
  }

  renderSignalsFeed();
  if (AppState.connected) {
    startAutoStreamPrimer();
  }
}

function startAutoStreamPrimer() {
  if (AppState._primerInterval) return;
  AppState._primerInterval = setInterval(() => {
    if (!AppState.connected) return;
    const unstreamed = (AppState.allAssets || []).filter(a => {
      const sym = a.symbol;
      const isWatched = AppState.watchedMarkets[sym] !== false;
      const hasPrice = AppState.prices[sym] && AppState.prices[sym] > 0.0001;
      return isWatched && !hasPrice;
    });

    if (unstreamed.length > 0) {
      for (let i = 0; i < Math.min(2, unstreamed.length); i++) {
        const target = unstreamed[i];
        if (window.pywebview && window.pywebview.api && window.pywebview.api.prime_asset_stream) {
          window.pywebview.api.prime_asset_stream(target.symbol);
        }
      }
    }
  }, 1000);
}

function sanitizeId(str) {
  return (str || '').toLowerCase().replace(/[^a-z0-9]/g, '_');
}

function formatPrice(symbol, price) {
  let num = price;
  if (typeof num !== 'number') {
    num = parseFloat(num);
    if (isNaN(num)) return price;
  }
  // If exact precision is registered for this asset, use it directly!
  if (AppState.precisions) {
    let prec = AppState.precisions[symbol];
    if (prec === undefined && symbol) {
      const clean = symbol.replace(/\s*\(OTC\)/i, '').trim();
      prec = AppState.precisions[clean] !== undefined ? AppState.precisions[clean] : AppState.precisions[clean + ' (OTC)'];
    }
    if (prec !== undefined) {
      if (num >= 1000 && !symbol.includes('/') && !symbol.includes('OTC')) {
        return num.toLocaleString('en-US', { minimumFractionDigits: prec, maximumFractionDigits: prec });
      }
      return num.toFixed(prec);
    }
  }
  const sym = (symbol || '').toUpperCase();
  if (sym.includes('BTC') || sym.includes('ETH') || sym.includes('SOL') || sym.includes('XAU') || 
      sym.includes('INDEX') || sym.includes('STOCK') || sym.includes('US500') || sym.includes('NAS')) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (sym.includes('JPY')) {
    return num.toFixed(3);
  }
  if (sym.includes('INR') || sym.includes('BRL') || sym.includes('PKR') || 
      sym.includes('BDT') || sym.includes('EGP') || sym.includes('PHP') || 
      sym.includes('TRY') || sym.includes('IDR') || sym.includes('ZAR') || sym.includes('MXN') ||
      sym.includes('ARS') || sym.includes('COP') || sym.includes('NGN') || sym.includes('DZD')) {
    return num.toFixed(4);
  }
  if (num >= 1000) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (num >= 50) {
    return num.toFixed(4);
  }
  if (num < 10) {
    return num.toFixed(5);
  }
  return num.toFixed(4);
}

// ============================================================================
// Strategy Performance Leaderboard
// ============================================================================
function loadStrategyLeaderboard() {
  const container = document.getElementById('strategy-leaderboard-container');
  if (!container) return;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_performance_stats) {
    window.pywebview.api.get_performance_stats().then(stats => {
      const breakdown = (stats && stats.strategy_breakdown) || [];
      if (breakdown.length === 0) {
        container.innerHTML = `
          <div style="font-size: 11px; color: var(--text-dim); text-align: center; padding: 12px;">
            No completed trade outcomes recorded for this session yet.
          </div>
        `;
        return;
      }

      const medals = ['🥇', '🥈', '🥉'];
      let html = '';
      breakdown.forEach((item, idx) => {
        const rankBadge = idx < 3 ? medals[idx] : `<span style="font-size: 10px; opacity: 0.75; font-weight: 800;">#${idx + 1}</span>`;
        const wrVal = parseFloat(item.win_rate) || 0;
        const wrColor = wrVal >= 60 ? 'var(--emerald)' : (wrVal >= 45 ? '#38bdf8' : 'var(--rose)');
        const wrBg = wrVal >= 60 ? 'rgba(16, 185, 129, 0.12)' : (wrVal >= 45 ? 'rgba(56, 189, 248, 0.12)' : 'rgba(244, 63, 94, 0.12)');
        const wrBorder = wrVal >= 60 ? 'rgba(16, 185, 129, 0.35)' : (wrVal >= 45 ? 'rgba(56, 189, 248, 0.35)' : 'rgba(244, 63, 94, 0.35)');

        html += `
          <div class="leaderboard-item" title="Rank #${idx + 1}: ${escapeHtml(item.strategy_name)} (${item.win_rate}% Win Rate)">
            <span class="leaderboard-rank">${rankBadge}</span>
            <span class="leaderboard-name" title="${escapeHtml(item.strategy_name)}">${escapeHtml(item.strategy_name)}</span>
            <div class="leaderboard-stats">
              <span class="leaderboard-wr" style="color: ${wrColor}; background: ${wrBg}; border: 1px solid ${wrBorder};">${item.win_rate}%</span>
              <span class="leaderboard-counts">(${item.wins}W / ${item.losses}L)</span>
            </div>
          </div>
        `;
      });
      container.innerHTML = html;
    }).catch(e => console.debug('[LEADERBOARD] Fetch error:', e));
  }
}
window.loadStrategyLeaderboard = loadStrategyLeaderboard;

// ============================================================================
// Platform Preferences & Feature Toggles
// ============================================================================
window.toggleVoicePref = function(checkbox) {
  AppState.voiceEnabled = checkbox.checked;
  localStorage.setItem('tradepulse_voice_enabled', checkbox.checked ? 'true' : 'false');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_feature_toggle) {
    window.pywebview.api.update_feature_toggle('voice_alerts', checkbox.checked);
  }
  showToast(`Voice Alerts ${checkbox.checked ? 'ENABLED' : 'DISABLED'}`, checkbox.checked ? 'success' : 'info');
};

window.testVoiceAlert = function() {
  VoiceEngine.speak('Trade alert: CALL on Euro US Dollar OTC. Expiry 2 Minutes.');
};

window.toggleFeaturePref = function(featureName, isChecked) {
  if (featureName === 'pre_alerts') AppState.preAlertsEnabled = isChecked;
  if (featureName === 'otc_flatline_guard') AppState.otcFlatlineGuardEnabled = isChecked;
  if (featureName === 'confluence_scanner') AppState.confluenceScannerEnabled = isChecked;

  localStorage.setItem(`tradepulse_${featureName}`, isChecked ? 'true' : 'false');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_feature_toggle) {
    window.pywebview.api.update_feature_toggle(featureName, isChecked);
  }
  showToast(`${featureName.replace(/_/g, ' ').toUpperCase()}: ${isChecked ? 'ON' : 'OFF'}`, 'info');
};

// Window resize handler to keep broker dock and canvas graphs crisp
let resizeDebounceTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeDebounceTimer);
  resizeDebounceTimer = setTimeout(() => {
    syncBrokerStationLayout(true);
    if (AppState.activeView === 'history') {
      renderEquityCurve();
    }
    if (AppState.activeView === 'chart' && window.LiveChartEngine) {
      window.LiveChartEngine.resize();
    }
  }, 60);
});

// ============================================================================
// Real-Time Interactive Live Chart Station Controller
// ============================================================================
function initLiveChartStation() {
  if (window.LiveChartEngine) {
    window.LiveChartEngine.init();
    populateChartAssetSelector();
    populateChartQuickWatchlist();
    const sym = AppState.selectedMarket || window.LiveChartEngine.activeSymbol || 'EUR/USD (OTC)';
    const tf = window.LiveChartEngine.activeTimeframe || '1M';

    // If chart already has candles for the current symbol, just resize and resume — no full reload
    const inst = window.LiveChartEngine.instance;
    const hasExistingCandles = inst && inst.candles && inst.candles.length > 0 && inst.symbol === sym;
    if (hasExistingCandles) {
      // Chart is returning from tab switch — preserve history, just resize
      setTimeout(() => {
        if (window.LiveChartEngine) window.LiveChartEngine.resize();
      }, 50);
    } else {
      // First init or symbol changed — load candles fresh
      window.LiveChartEngine.setSymbol(sym, tf);
      setTimeout(() => {
        if (window.LiveChartEngine) window.LiveChartEngine.resize();
      }, 50);
    }
  }
}
window.initLiveChartStation = initLiveChartStation;

function populateChartAssetSelector() {
  const sel = document.getElementById('chart-asset-select');
  if (!sel) return;

  const currentVal = sel.value || AppState.selectedMarket || 'EUR/USD (OTC)';
  const assets = AppState.assets && AppState.assets.length > 0 ? AppState.assets : [
    { symbol: 'EUR/USD (OTC)', name: 'EUR/USD (OTC)', category: 'Currencies' },
    { symbol: 'USD/BRL (OTC)', name: 'USD/BRL (OTC)', category: 'Currencies' },
    { symbol: 'GBP/USD (OTC)', name: 'GBP/USD (OTC)', category: 'Currencies' },
    { symbol: 'USD/INR (OTC)', name: 'USD/INR (OTC)', category: 'Currencies' },
    { symbol: 'EUR/USD', name: 'EUR/USD', category: 'Currencies' }
  ];

  let html = '';
  // Group by OTC vs Real
  const otcAssets = assets.filter(a => a.symbol.includes('(OTC)') || a.symbol.toLowerCase().includes('_otc'));
  const realAssets = assets.filter(a => !a.symbol.includes('(OTC)') && !a.symbol.toLowerCase().includes('_otc'));

  if (otcAssets.length > 0) {
    html += '<optgroup label="🌙 Quotex OTC Assets">';
    otcAssets.forEach(a => {
      const payout = AppState.payouts[a.symbol] ? ` (${AppState.payouts[a.symbol]}%)` : '';
      const price = AppState.prices[a.symbol] ? ` - ${formatPrice(a.symbol, AppState.prices[a.symbol])}` : '';
      html += `<option value="${escapeHtml(a.symbol)}">${escapeHtml(a.symbol)}${payout}${price}</option>`;
    });
    html += '</optgroup>';
  }

  if (realAssets.length > 0) {
    html += '<optgroup label="🏛️ Real Market Assets">';
    realAssets.forEach(a => {
      const payout = AppState.payouts[a.symbol] ? ` (${AppState.payouts[a.symbol]}%)` : '';
      const price = AppState.prices[a.symbol] ? ` - ${formatPrice(a.symbol, AppState.prices[a.symbol])}` : '';
      html += `<option value="${escapeHtml(a.symbol)}">${escapeHtml(a.symbol)}${payout}${price}</option>`;
    });
    html += '</optgroup>';
  }

  sel.innerHTML = html;
  if (currentVal) sel.value = currentVal;
}
window.populateChartAssetSelector = populateChartAssetSelector;

function populateChartQuickWatchlist() {
  const container = document.getElementById('chart-quick-watchlist');
  if (!container) return;

  const quickPairs = ['EUR/USD (OTC)', 'USD/BRL (OTC)', 'GBP/USD (OTC)', 'USD/INR (OTC)', 'EUR/USD', 'GBP/USD'];
  const curSym = window.LiveChartEngine ? window.LiveChartEngine.activeSymbol : 'EUR/USD (OTC)';

  let html = '';
  quickPairs.forEach(sym => {
    const isActive = sym === curSym;
    const payout = AppState.payouts[sym] ? `${AppState.payouts[sym]}%` : '85%';
    html += `
      <button type="button" class="btn-quick-chip ${isActive ? 'active' : ''}" onclick="onStationAssetChanged('${sym}')">
        <span>${sym}</span>
        <span class="chip-payout">${payout}</span>
      </button>
    `;
  });
  container.innerHTML = html;
}
window.populateChartQuickWatchlist = populateChartQuickWatchlist;

// Live Candle Countdown Loop
setInterval(() => {
  const textEl = document.getElementById('chart-countdown-text');
  if (!textEl) return;
  const tf = (window.LiveChartEngine && window.LiveChartEngine.activeTimeframe) || '1M';
  let periodSec = 60;
  if (tf === '3M') periodSec = 180;
  else if (tf === '5M') periodSec = 300;
  else if (tf === '15M') periodSec = 900;

  const nowSec = Math.floor(Date.now() / 1000);
  const remaining = periodSec - (nowSec % periodSec);
  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  textEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}, 1000);

// ============================================================================
// Institutional Safeguards & Filters Controllers
// ============================================================================

function toggleAdvancedFilter(category, field, value) {
  if (!AppState.advancedFilters) AppState.advancedFilters = {};
  if (!AppState.advancedFilters[category]) AppState.advancedFilters[category] = {};
  AppState.advancedFilters[category][field] = value;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      [category]: { [field]: value }
    }).then(res => {
      if (res && res.config) {
        AppState.advancedFilters = res.config;
      }
      updateSafeguardsStrip();
    });
  } else {
    updateSafeguardsStrip();
  }
}
window.toggleAdvancedFilter = toggleAdvancedFilter;

function updateNewsConfig() {
  const beforeVal = parseInt(document.getElementById('pref-news-before')?.value || '30', 10);
  const afterVal = parseInt(document.getElementById('pref-news-after')?.value || '30', 10);
  const impactHigh = !!document.getElementById('pref-news-impact-high')?.checked;
  const impactMed = !!document.getElementById('pref-news-impact-med')?.checked;
  const impactLow = !!document.getElementById('pref-news-impact-low')?.checked;
  const bypassOtc = !!document.getElementById('pref-news-bypass-otc')?.checked;

  const payload = {
    pause_before_minutes: beforeVal,
    pause_after_minutes: afterVal,
    impact_high: impactHigh,
    impact_medium: impactMed,
    impact_low: impactLow,
    pause_otc: !bypassOtc
  };

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      news_calendar: payload
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      updateSafeguardsStrip();
    });
  }
}
window.updateNewsConfig = updateNewsConfig;

function refreshUpcomingNews() {
  const listEl = document.getElementById('pref-news-upcoming-list');
  if (listEl) listEl.innerHTML = '<div class="news-loading-placeholder">Refreshing institutional calendar...</div>';

  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_upcoming_news_events) {
    window.pywebview.api.get_upcoming_news_events(6).then(events => {
      AppState.upcomingNews = events || [];
      renderUpcomingNewsList(AppState.upcomingNews);
      updateSafeguardsStrip();
    });
  }
}
window.refreshUpcomingNews = refreshUpcomingNews;

function renderUpcomingNewsList(events) {
  const listEl = document.getElementById('pref-news-upcoming-list');
  if (!listEl) return;

  if (!events || events.length === 0) {
    listEl.innerHTML = '<div class="news-loading-placeholder">No upcoming high/medium impact macro releases scheduled today.</div>';
    return;
  }

  listEl.innerHTML = '';
  events.forEach(ev => {
    const item = document.createElement('div');
    item.className = 'news-event-item';

    const impact = (ev.impact || 'HIGH').toUpperCase();
    let impactTagClass = 'tag-high';
    if (impact === 'MEDIUM') impactTagClass = 'tag-med';
    else if (impact === 'LOW') impactTagClass = 'tag-low';

    let countdownText = '';
    const mins = ev.mins_until;
    if (mins === undefined || mins === null) {
      countdownText = ev.time_str || '--';
    } else if (mins > 0) {
      countdownText = mins >= 60 ? `in ${Math.floor(mins/60)}h ${mins%60}m` : `in ${mins}m`;
    } else if (mins === 0) {
      countdownText = '⚡ NOW';
    } else {
      countdownText = `${Math.abs(mins)}m ago`;
    }

    item.innerHTML = `
      <div style="display: flex; align-items: center; min-width: 0; gap: 4px;">
        <span class="news-event-curr">${escapeHtml(ev.currency || 'USD')}</span>
        <span class="impact-tag ${impactTagClass}" style="padding: 1px 5px; font-size: 9px;">${impact}</span>
        <span class="news-event-title" title="${escapeHtml(ev.title || '')}">${escapeHtml(ev.title || 'Macro Release')}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="news-countdown-badge">${countdownText}</span>
      </div>
    `;
    listEl.appendChild(item);
  });
}
window.renderUpcomingNewsList = renderUpcomingNewsList;

function updateQuantEVConfig() {
  const positiveOnly = !!document.getElementById('pref-ev-positive-only')?.checked;
  const minConf = parseFloat(document.getElementById('pref-ev-conf-slider')?.value || '55');
  const mode = document.getElementById('pref-ev-mode')?.value || 'quant';

  const payload = {
    require_positive_ev: positiveOnly,
    min_confidence: minConf,
    engine_mode: mode
  };

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      quant_ev: payload
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      updateSafeguardsStrip();
    });
  }
}
window.updateQuantEVConfig = updateQuantEVConfig;

function updateRiskConfig() {
  const baseStake = parseFloat(document.getElementById('pref-risk-base-stake')?.value || '10.0');
  const martToggle = !!document.getElementById('pref-risk-martingale-toggle')?.checked;
  const martMult = parseFloat(document.getElementById('pref-risk-martingale-mult')?.value || '2.0');
  const martSteps = parseInt(document.getElementById('pref-risk-martingale-steps')?.value || '3', 10);
  const tpToggle = !!document.getElementById('pref-risk-tp-toggle')?.checked;
  const tpAmount = parseFloat(document.getElementById('pref-risk-tp-amount')?.value || '100.0');
  const slToggle = !!document.getElementById('pref-risk-sl-toggle')?.checked;
  const slAmount = parseFloat(document.getElementById('pref-risk-sl-amount')?.value || '50.0');

  const payload = {
    base_stake: baseStake,
    martingale_enabled: martToggle,
    martingale_multiplier: martMult,
    martingale_max_steps: martSteps,
    daily_tp_enabled: tpToggle,
    daily_tp_amount: tpAmount,
    daily_sl_enabled: slToggle,
    daily_sl_amount: slAmount
  };

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      risk_manager: payload
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      if (window.pywebview.api.get_risk_session_metrics) {
        window.pywebview.api.get_risk_session_metrics().then(metrics => {
          AppState.riskMetrics = metrics;
          updateRiskMetricsUI(metrics);
          updateSafeguardsStrip();
        });
      }
    });
  }
}
window.updateRiskConfig = updateRiskConfig;

function resetDailyRiskSession() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.reset_daily_risk_session) {
    window.pywebview.api.reset_daily_risk_session().then(res => {
      if (res && res.metrics) {
        AppState.riskMetrics = res.metrics;
        updateRiskMetricsUI(res.metrics);
        updateSafeguardsStrip();
      }
      updateToolStatusUI(true);
    });
  }
}
window.resetDailyRiskSession = resetDailyRiskSession;

function updateRiskMetricsUI(metrics) {
  if (!metrics) return;
  const pnlEl = document.getElementById('risk-session-pnl');
  const recEl = document.getElementById('risk-session-record');
  const stakeEl = document.getElementById('risk-session-stake');

  const pnl = metrics.daily_pnl || 0.0;
  if (pnlEl) {
    pnlEl.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
    pnlEl.style.color = pnl > 0 ? 'var(--emerald)' : (pnl < 0 ? '#ef4444' : 'var(--text-bright)');
  }
  if (recEl) {
    recEl.textContent = `${metrics.trades_count || 0} Trades (${metrics.consecutive_losses || 0} Streak)`;
  }
  if (stakeEl) {
    const step = metrics.current_martingale_step || 1;
    stakeEl.textContent = `$${(metrics.next_recommended_stake || 10).toFixed(2)}${step > 1 ? ' (Step ' + step + ')' : ''}`;
  }
}
window.updateRiskMetricsUI = updateRiskMetricsUI;

function toggleScheduleDay(day) {
  if (!AppState.advancedFilters?.session_scheduler) {
    AppState.advancedFilters = AppState.advancedFilters || {};
    AppState.advancedFilters.session_scheduler = { allowed_days: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] };
  }
  let allowed = AppState.advancedFilters.session_scheduler.allowed_days || ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
  const idx = allowed.indexOf(day);
  if (idx !== -1) {
    if (allowed.length > 1) {
      allowed.splice(idx, 1);
    }
  } else {
    allowed.push(day);
  }
  AppState.advancedFilters.session_scheduler.allowed_days = allowed;

  const pills = document.querySelectorAll('#schedule-day-pills .day-pill');
  pills.forEach(pill => {
    const d = pill.getAttribute('data-day');
    if (allowed.includes(d)) {
      pill.classList.add('active');
    } else {
      pill.classList.remove('active');
    }
  });

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      session_scheduler: { allowed_days: allowed }
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      updateSafeguardsStrip();
    });
  }
}
window.toggleScheduleDay = toggleScheduleDay;

function updateScheduleConfig() {
  const start = document.getElementById('pref-schedule-start')?.value || '00:00';
  const end = document.getElementById('pref-schedule-end')?.value || '23:59';

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      session_scheduler: { start_time: start, end_time: end }
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      updateSafeguardsStrip();
    });
  }
}
window.updateScheduleConfig = updateScheduleConfig;

function setScheduleTimezone(isUtc) {
  const utcPill = document.getElementById('tz-pill-utc');
  const localPill = document.getElementById('tz-pill-local');
  if (utcPill && localPill) {
    if (isUtc) {
      utcPill.classList.add('active');
      localPill.classList.remove('active');
    } else {
      localPill.classList.add('active');
      utcPill.classList.remove('active');
    }
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_advanced_filters_config) {
    window.pywebview.api.update_advanced_filters_config({
      session_scheduler: { use_utc: isUtc }
    }).then(res => {
      if (res && res.config) AppState.advancedFilters = res.config;
      updateSafeguardsStrip();
    });
  }
}
window.setScheduleTimezone = setScheduleTimezone;

function applyAdvancedFiltersToUI(filters) {
  if (!filters) return;

  // News
  if (filters.news_calendar) {
    const nc = filters.news_calendar;
    const ncToggle = document.getElementById('pref-news-toggle');
    if (ncToggle) ncToggle.checked = !!nc.enabled;
    const ncBefore = document.getElementById('pref-news-before');
    if (ncBefore && nc.pause_before_minutes) ncBefore.value = nc.pause_before_minutes;
    const ncAfter = document.getElementById('pref-news-after');
    if (ncAfter && nc.pause_after_minutes) ncAfter.value = nc.pause_after_minutes;
    const ncHigh = document.getElementById('pref-news-impact-high');
    if (ncHigh) ncHigh.checked = !!nc.impact_high;
    const ncMed = document.getElementById('pref-news-impact-med');
    if (ncMed) ncMed.checked = !!nc.impact_medium;
    const ncLow = document.getElementById('pref-news-impact-low');
    if (ncLow) ncLow.checked = !!nc.impact_low;
    const ncOtc = document.getElementById('pref-news-bypass-otc');
    if (ncOtc) ncOtc.checked = !nc.pause_otc;
  }

  // Quant EV
  if (filters.quant_ev) {
    const qe = filters.quant_ev;
    const qeToggle = document.getElementById('pref-ev-toggle');
    if (qeToggle) qeToggle.checked = !!qe.enabled;
    const qePos = document.getElementById('pref-ev-positive-only');
    if (qePos) qePos.checked = !!qe.require_positive_ev;
    const qeSlider = document.getElementById('pref-ev-conf-slider');
    const qeLabel = document.getElementById('pref-ev-conf-label');
    if (qeSlider && qe.min_confidence) {
      qeSlider.value = qe.min_confidence;
      if (qeLabel) qeLabel.textContent = `${qe.min_confidence}%`;
    }
    const qeMode = document.getElementById('pref-ev-mode');
    if (qeMode && qe.engine_mode) qeMode.value = qe.engine_mode;
  }

  // Risk Manager
  if (filters.risk_manager) {
    const rm = filters.risk_manager;
    const rmToggle = document.getElementById('pref-risk-toggle');
    if (rmToggle) rmToggle.checked = !!rm.enabled;
    const rmBase = document.getElementById('pref-risk-base-stake');
    if (rmBase && rm.base_stake) rmBase.value = rm.base_stake;
    const rmMart = document.getElementById('pref-risk-martingale-toggle');
    if (rmMart) rmMart.checked = !!rm.martingale_enabled;
    const rmMini = document.getElementById('pref-risk-martingale-mult');
    if (rmMini && rm.martingale_multiplier) rmMini.value = rm.martingale_multiplier;
    const rmSteps = document.getElementById('pref-risk-martingale-steps');
    if (rmSteps && rm.martingale_max_steps) rmSteps.value = rm.martingale_max_steps;
    const rmTpToggle = document.getElementById('pref-risk-tp-toggle');
    if (rmTpToggle) rmTpToggle.checked = !!rm.daily_tp_enabled;
    const rmTpAmt = document.getElementById('pref-risk-tp-amount');
    if (rmTpAmt && rm.daily_tp_amount) rmTpAmt.value = rm.daily_tp_amount;
    const rmSlToggle = document.getElementById('pref-risk-sl-toggle');
    if (rmSlToggle) rmSlToggle.checked = !!rm.daily_sl_enabled;
    const rmSlAmt = document.getElementById('pref-risk-sl-amount');
    if (rmSlAmt && rm.daily_sl_amount) rmSlAmt.value = rm.daily_sl_amount;
  }

  // Session Scheduler
  if (filters.session_scheduler) {
    const ss = filters.session_scheduler;
    const ssToggle = document.getElementById('pref-schedule-toggle');
    if (ssToggle) ssToggle.checked = !!ss.enabled;
    const ssStart = document.getElementById('pref-schedule-start');
    if (ssStart && ss.start_time) ssStart.value = ss.start_time;
    const ssEnd = document.getElementById('pref-schedule-end');
    if (ssEnd && ss.end_time) ssEnd.value = ss.end_time;

    const utcPill = document.getElementById('tz-pill-utc');
    const localPill = document.getElementById('tz-pill-local');
    if (utcPill && localPill) {
      if (ss.use_utc !== false) {
        utcPill.classList.add('active');
        localPill.classList.remove('active');
      } else {
        localPill.classList.add('active');
        utcPill.classList.remove('active');
      }
    }

    if (ss.allowed_days) {
      const pills = document.querySelectorAll('#schedule-day-pills .day-pill');
      pills.forEach(pill => {
        const d = pill.getAttribute('data-day');
        if (ss.allowed_days.includes(d)) {
          pill.classList.add('active');
        } else {
          pill.classList.remove('active');
        }
      });
    }
  }
}
window.applyAdvancedFiltersToUI = applyAdvancedFiltersToUI;

function updateSafeguardsStrip() {
  const f = AppState.advancedFilters || {};

  // 1. News
  const newsDot = document.getElementById('dot-news');
  const newsLabel = document.getElementById('label-news');
  const newsEnabled = f.news_calendar ? f.news_calendar.enabled : true;
  if (newsDot && newsLabel) {
    if (newsEnabled) {
      newsDot.className = 'chip-dot dot-active';
      newsLabel.textContent = 'News Guard: Active';
    } else {
      newsDot.className = 'chip-dot dot-off';
      newsLabel.textContent = 'News Guard: Off';
    }
  }

  // 2. Schedule
  const schedDot = document.getElementById('dot-schedule');
  const schedLabel = document.getElementById('label-schedule');
  const schedBannerText = document.getElementById('pref-schedule-status-text');
  const schedBannerDot = document.getElementById('pref-schedule-dot');
  const schedEnabled = f.session_scheduler ? f.session_scheduler.enabled : false;

  if (schedDot && schedLabel) {
    if (!schedEnabled) {
      schedDot.className = 'chip-dot dot-active';
      schedLabel.textContent = 'Session: 24/7 Scanning';
      if (schedBannerText) schedBannerText.textContent = 'Schedule disabled (24/7 scanning active)';
      if (schedBannerDot) schedBannerDot.className = 'schedule-status-dot dot-active';
    } else {
      const ss = f.session_scheduler;
      schedDot.className = 'chip-dot dot-active';
      schedLabel.textContent = `Session: Window (${ss.start_time || '00:00'}-${ss.end_time || '23:59'})`;
      if (schedBannerText) schedBannerText.textContent = `Schedule active: Window ${ss.start_time || '00:00'} - ${ss.end_time || '23:59'} (${ss.use_utc ? 'UTC' : 'Local'})`;
      if (schedBannerDot) schedBannerDot.className = 'schedule-status-dot dot-active';
    }
  }

  // 3. EV Quant
  const evDot = document.getElementById('dot-ev');
  const evLabel = document.getElementById('label-ev');
  const evEnabled = f.quant_ev ? f.quant_ev.enabled : true;
  if (evDot && evLabel) {
    if (evEnabled) {
      const minC = f.quant_ev?.min_confidence || 55;
      evDot.className = 'chip-dot dot-active';
      evLabel.textContent = `EV Guard: Active (EV > 0, ${minC}%)`;
    } else {
      evDot.className = 'chip-dot dot-off';
      evLabel.textContent = 'EV Guard: Off';
    }
  }

  // 4. Risk
  const riskDot = document.getElementById('dot-risk');
  const riskLabel = document.getElementById('label-risk');
  const riskEnabled = f.risk_manager ? f.risk_manager.enabled : true;
  if (riskDot && riskLabel) {
    if (!riskEnabled) {
      riskDot.className = 'chip-dot dot-off';
      riskLabel.textContent = 'Risk Suite: Off';
    } else {
      const metrics = AppState.riskMetrics || {};
      if (metrics.circuit_breaker_active) {
        riskDot.className = 'chip-dot dot-alert';
        riskLabel.textContent = `Risk: PAUSED (${metrics.circuit_breaker_reason || 'Circuit Breaker Hit'})`;
      } else {
        riskDot.className = 'chip-dot dot-active';
        const pnl = metrics.daily_pnl || 0;
        const stake = metrics.next_recommended_stake || f.risk_manager?.base_stake || 10;
        riskLabel.textContent = `Risk: Rec $${stake.toFixed(0)} | PnL ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
      }
    }
  }
}
window.updateSafeguardsStrip = updateSafeguardsStrip;

function scrollToPrefCard(cardId) {
  setTimeout(() => {
    const el = document.getElementById(cardId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.transition = 'box-shadow 0.3s ease, border-color 0.3s ease';
      el.style.borderColor = 'var(--cyan-bright)';
      el.style.boxShadow = '0 0 20px rgba(0, 240, 255, 0.35)';
      setTimeout(() => {
        el.style.borderColor = '';
        el.style.boxShadow = '';
      }, 1500);
    }
  }, 100);
}
window.scrollToPrefCard = scrollToPrefCard;

window.onCircuitBreakerTriggered = function(metrics) {
  console.warn('[CIRCUIT BREAKER TRIGGERED]', metrics);
  AppState.riskMetrics = metrics;
  updateRiskMetricsUI(metrics);
  updateSafeguardsStrip();
  updateToolStatusUI(false);

  const reason = metrics.circuit_breaker_reason || 'Daily Risk Limit Reached';
  const existingToast = document.querySelector('.circuit-breaker-alert-toast');
  if (existingToast) existingToast.remove();

  const banner = document.createElement('div');
  banner.className = 'circuit-breaker-alert-toast';
  banner.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 99999;
    background: rgba(239, 68, 68, 0.95); backdrop-filter: blur(10px);
    color: #fff; padding: 14px 20px; border-radius: 8px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.6), 0 0 20px rgba(239,68,68,0.5);
    border: 1px solid rgba(255,255,255,0.2); max-width: 420px;
    display: flex; flex-direction: column; gap: 8px; font-family: var(--font-sans);
  `;
  banner.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between;">
      <strong style="font-size: 13px; display: flex; align-items: center; gap: 6px;">
        🛑 CIRCUIT BREAKER ACTIVATED
      </strong>
      <button style="background: transparent; border: none; color: #fff; cursor: pointer; font-size: 16px;" onclick="this.parentElement.parentElement.remove()">✕</button>
    </div>
    <div style="font-size: 11px; opacity: 0.95; line-height: 1.4;">
      ${escapeHtml(reason)}. Signal scanner has been automatically paused to protect capital.
    </div>
    <div style="display: flex; gap: 8px; margin-top: 4px;">
      <button style="background: #fff; color: #b91c1c; border: none; border-radius: 4px; padding: 4px 10px; font-size: 10px; font-weight: 700; cursor: pointer;" onclick="switchView('preferences'); scrollToPrefCard('pref-card-risk'); this.closest('.circuit-breaker-alert-toast').remove();">
        ⚙️ Manage Risk Session
      </button>
      <button style="background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; padding: 4px 10px; font-size: 10px; font-weight: 600; cursor: pointer;" onclick="resetDailyRiskSession(); this.closest('.circuit-breaker-alert-toast').remove();">
        🔄 Reset Session Now
      </button>
    </div>
  `;
  document.body.appendChild(banner);
};

// ============================================================================
// Telegram Bot & Signal Manager
// ============================================================================
const DEFAULT_TELEGRAM_TEMPLATES = {
  signal: `🚀 <b>SIGNAL ALERT: {strategy}</b>\n────────────────────────\n📊 <b>Asset:</b> <code>{asset}</code>\n💰 <b>OTC Payout:</b> <b>{payout}%</b>\n{arrow} <b>Direction:</b> <b>{direction}</b>\n⏱ <b>Timeframe:</b> <b>{timeframe}</b>\n⌛ <b>Expiry Duration:</b> <b>{expiry} Mins</b>\n🕒 <b>Entry Time:</b> <b>Next Candle Open (00s) | {entry_time} IST</b>\n💵 <b>Entry Price:</b> <code>{entry_price}</code>\n━━━━━━━━━━━━━━━━━━━━\n{confluence_section}🎯 <b>Setup Quality Score:</b> <b>{confidence}% ({tier})</b>\n{stake_line}{ev_line}⏰ <b>Expiry Target:</b> <b>{expiry_time} IST</b>\n🔒 <i>TradePulse VIP Institutional Signal</i>`,
  pre_signal: `⚡ <b>PRE-SIGNAL RADAR: PREPARE ENTRY</b>\n────────────────────────\n📊 <b>Asset:</b> <code>{asset}</code>\n🎯 <b>Direction:</b> <b>{dir_badge}</b>\n⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry}m)\n💰 <b>Payout:</b> <b>{payout}%</b>\n⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n🧠 <b>Forming Pattern:</b> {strategy}\n{stake_line}────────────────────────\n<i>Prepare pair & stake in Quotex. Official entry fires on candle close.</i>`,
  outcome: `{header}\n────────────────────────\n📊 <b>Asset:</b> <code>{asset}</code>\n🎯 <b>Strategy:</b> <code>{strategy}</code>\n📌 <b>Direction:</b> <b>{direction}</b>\n🏁 <b>Result:</b> <b>{outcome_badge}</b>\n━━━━━━━━━━━━━━━━━━━━\n💵 <b>Entry Strike:</b> <code>{entry_price}</code>\n🏁 <b>Exit Price:</b>   <code>{exit_price}</code>\n{pnl_text}\n━━━━━━━━━━━━━━━━━━━━\n🔒 <i>TradePulse 24/7 Real-Time Outcome Verification</i>`,
  circuit_breaker: `🛑 <b>TRADEPULSE CIRCUIT BREAKER ACTIVATED</b>\n━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>Signal Scanner Auto-Paused</b>\n• <b>Trigger Reason:</b> <b>{cb_reason}</b>\n• <b>Session Net PnL:</b> <b>{net_pnl}</b>\n• <b>Total Trades:</b> <b>{total_trades}</b>\n━━━━━━━━━━━━━━━━━━━━\n🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>`
};

const TelegramManagerState = {
  activeTab: 'bot',
  bot_token: '',
  polling_enabled: true,
  channels: [],
  rules: {
    signals: true,
    pre_signals: true,
    outcomes: true,
    circuit_breaker: true,
    news: true,
    attach_charts: true,
    min_score: 80.0,
    min_payout: 75.0
  },
  templates: { ...DEFAULT_TELEGRAM_TEMPLATES },
  activeTemplateKey: 'signal',
  bot_verified: false,
  bot_info: null
};

const TG_TEMPLATE_TOKENS = {
  signal: [
    { token: '{asset}', desc: 'Asset Symbol (e.g. EUR/USD (OTC))' },
    { token: '{direction}', desc: 'CALL or PUT' },
    { token: '{arrow}', desc: '📈 or 📉' },
    { token: '{payout}', desc: 'OTC Payout (e.g. 92%)' },
    { token: '{confidence}', desc: 'Setup Score (e.g. 94)' },
    { token: '{strategy}', desc: 'Strategy Name' },
    { token: '{timeframe}', desc: 'Timeframe (e.g. 1M)' },
    { token: '{duration}', desc: 'Duration in Mins (e.g. 1)' },
    { token: '{entry_time}', desc: 'Entry Time in IST' },
    { token: '{entry_price}', desc: 'Strike Price' },
    { token: '{rec_stake}', desc: 'Calculated Stake ($)' },
    { token: '{martingale_step}', desc: 'Martingale Step' },
    { token: '{ev_edge}', desc: 'Quant EV Mathematical Edge' },
    { token: '{header}', desc: 'Status Title Header' }
  ],
  pre_signal: [
    { token: '{asset}', desc: 'Asset Symbol' },
    { token: '{direction}', desc: 'CALL or PUT' },
    { token: '{timeframe}', desc: 'Candle Timeframe' },
    { token: '{expiry_minutes}', desc: 'Expiry Duration' },
    { token: '{payout}', desc: 'Current Payout %' },
    { token: '{remaining_seconds}', desc: 'Remaining Seconds' },
    { token: '{strategy}', desc: 'Forming Pattern' },
    { token: '{rec_stake}', desc: 'Recommended Stake' },
    { token: '{martingale_step}', desc: 'Step Number' },
    { token: '{ev_edge}', desc: 'EV Edge' }
  ],
  outcome: [
    { token: '{header}', desc: 'Result Header Banner' },
    { token: '{asset}', desc: 'Asset Symbol' },
    { token: '{strategy}', desc: 'Strategy Name' },
    { token: '{direction}', desc: 'CALL or PUT' },
    { token: '{status}', desc: 'WIN / LOSS / DRAW' },
    { token: '{outcome_badge}', desc: 'WIN ✅ or LOSS ❌' },
    { token: '{entry_price}', desc: 'Entry Strike Price' },
    { token: '{exit_price}', desc: 'Expiry Exit Price' },
    { token: '{pnl_text}', desc: 'Profit / Return Line' }
  ],
  circuit_breaker: [
    { token: '{cb_reason}', desc: 'Circuit Breaker Trigger Reason' },
    { token: '{net_pnl}', desc: 'Net Session PnL ($)' },
    { token: '{win_rate}', desc: 'Session Win Rate %' },
    { token: '{total_trades}', desc: 'Total Trades Taken Today' }
  ]
};

function switchTelegramTab(tabId) {
  TelegramManagerState.activeTab = tabId;
  document.querySelectorAll('.tg-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tg-tab-pane').forEach(pane => pane.classList.remove('active'));

  const activeBtn = document.getElementById(`tg-subtab-${tabId}`);
  const activePane = document.getElementById(`tg-pane-${tabId}`);
  if (activeBtn) activeBtn.classList.add('active');
  if (activePane) activePane.classList.add('active');

  if (tabId === 'templates') {
    onSelectTelegramTemplate(TelegramManagerState.activeTemplateKey);
  } else if (tabId === 'broadcast') {
    updateBroadcastTargetSelector();
  }
}
window.switchTelegramTab = switchTelegramTab;

function toggleTokenVisibility(inputId) {
  const el = document.getElementById(inputId);
  if (el) {
    el.type = el.type === 'password' ? 'text' : 'password';
  }
}
window.toggleTokenVisibility = toggleTokenVisibility;

function initTelegramManagerState(data) {
  if (!data) return;
  TelegramManagerState.bot_token = data.bot_token || '';
  TelegramManagerState.polling_enabled = data.polling_enabled !== false;
  TelegramManagerState.channels = data.channels || [];
  if (data.rules) {
    TelegramManagerState.rules = { ...TelegramManagerState.rules, ...data.rules };
  }
  if (data.templates && typeof data.templates === 'object') {
    for (const [k, v] of Object.entries(data.templates)) {
      if (v && typeof v === 'string' && v.trim()) {
        TelegramManagerState.templates[k] = v;
      }
    }
  }
  renderTelegramManager();

  // If token is present, perform non-blocking background verification to show bot name
  if (TelegramManagerState.bot_token) {
    setTimeout(() => {
      try {
        verifyTelegramBotToken(true);
      } catch (e) {
        console.debug('[TELEGRAM] Token check note:', e);
      }
    }, 1200);
  }
}
window.initTelegramManagerState = initTelegramManagerState;

function renderTelegramManager() {
  // 1. Bot credentials inputs
  const tokenInput = document.getElementById('tg-mgr-token');
  if (tokenInput && !tokenInput.value) {
    tokenInput.value = TelegramManagerState.bot_token;
  }
  const pollCheck = document.getElementById('tg-mgr-polling');
  if (pollCheck) {
    pollCheck.checked = TelegramManagerState.polling_enabled;
  }

  // 2. Channels list
  renderTelegramChannelsList();

  // 3. Rules tab inputs
  const ruleSig = document.getElementById('tg-rule-signals');
  if (ruleSig) ruleSig.checked = TelegramManagerState.rules.signals !== false;
  const rulePre = document.getElementById('tg-rule-pre-signals');
  if (rulePre) rulePre.checked = TelegramManagerState.rules.pre_signals !== false;
  const ruleOut = document.getElementById('tg-rule-outcomes');
  if (ruleOut) ruleOut.checked = TelegramManagerState.rules.outcomes !== false;
  const ruleCb = document.getElementById('tg-rule-circuit-breaker');
  if (ruleCb) ruleCb.checked = TelegramManagerState.rules.circuit_breaker !== false;
  const ruleNews = document.getElementById('tg-rule-news');
  if (ruleNews) ruleNews.checked = TelegramManagerState.rules.news !== false;
  const ruleCharts = document.getElementById('tg-rule-charts');
  if (ruleCharts) ruleCharts.checked = TelegramManagerState.rules.attach_charts !== false;

  const minScore = document.getElementById('tg-rule-min-score');
  const scoreBadge = document.getElementById('tg-score-badge');
  if (minScore) {
    minScore.value = TelegramManagerState.rules.min_score !== undefined ? TelegramManagerState.rules.min_score : 80;
    if (scoreBadge) scoreBadge.textContent = `${minScore.value}%`;
  }
  const minPayout = document.getElementById('tg-rule-min-payout');
  const payoutBadge = document.getElementById('tg-payout-badge');
  if (minPayout) {
    minPayout.value = TelegramManagerState.rules.min_payout !== undefined ? TelegramManagerState.rules.min_payout : 75;
    if (payoutBadge) payoutBadge.textContent = `${minPayout.value}%`;
  }

  // 4. Update Broadcast Dropdown
  updateBroadcastTargetSelector();

  // 5. Update bot status badge
  updateBotBadgeUI();
}
window.renderTelegramManager = renderTelegramManager;

function updateBotBadgeUI() {
  const dot = document.getElementById('tg-manager-dot');
  const nameEl = document.getElementById('tg-manager-bot-name');
  const statusTag = document.getElementById('tg-bot-status-tag');

  if (TelegramManagerState.bot_verified && TelegramManagerState.bot_info) {
    const username = TelegramManagerState.bot_info.username ? `@${TelegramManagerState.bot_info.username}` : 'Online';
    if (dot) dot.style.background = 'var(--emerald)';
    if (nameEl) nameEl.textContent = `Connected (${username})`;
    if (statusTag) {
      statusTag.textContent = 'Active & Connected';
      statusTag.style.background = 'rgba(16, 185, 129, 0.15)';
      statusTag.style.color = 'var(--emerald)';
      statusTag.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    }
  } else if (TelegramManagerState.bot_token) {
    if (dot) dot.style.background = 'var(--amber)';
    if (nameEl) nameEl.textContent = 'Token Configured';
    if (statusTag) {
      statusTag.textContent = 'Unverified';
      statusTag.style.background = 'rgba(245, 158, 11, 0.12)';
      statusTag.style.color = 'var(--amber)';
      statusTag.style.borderColor = 'rgba(245, 158, 11, 0.3)';
    }
  } else {
    if (dot) dot.style.background = 'var(--text-muted)';
    if (nameEl) nameEl.textContent = 'No Bot Configured';
    if (statusTag) {
      statusTag.textContent = 'Not Configured';
      statusTag.style.background = 'rgba(255, 255, 255, 0.05)';
      statusTag.style.color = 'var(--text-muted)';
      statusTag.style.borderColor = 'var(--border-dim)';
    }
  }
}

function verifyTelegramBotToken(silent = false) {
  const tokenInput = document.getElementById('tg-mgr-token');
  const token = tokenInput ? tokenInput.value.trim() : TelegramManagerState.bot_token;

  if (!token) {
    if (!silent) showToast('Please enter a Telegram Bot Token first.', 'error');
    return;
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.test_telegram_bot_token) {
    window.pywebview.api.test_telegram_bot_token(token).then(res => {
      if (res && res.valid) {
        TelegramManagerState.bot_verified = true;
        TelegramManagerState.bot_info = res;
        updateBotBadgeUI();
        if (!silent) {
          showToast(`Bot Verified: @${res.username} (${res.first_name})`, 'success');
        }
      } else {
        TelegramManagerState.bot_verified = false;
        TelegramManagerState.bot_info = null;
        updateBotBadgeUI();
        if (!silent) {
          showToast(res && res.error ? `Verification Failed: ${res.error}` : 'Invalid Telegram Bot Token.', 'error');
        }
      }
    }).catch(err => {
      if (!silent) showToast(`Verification request error: ${err}`, 'error');
    });
  } else {
    if (!silent) showToast('Bridge API initializing, please wait...', 'info');
  }
}
window.verifyTelegramBotToken = verifyTelegramBotToken;

function saveTelegramBotCredentials(e) {
  if (e) e.preventDefault();
  const token = document.getElementById('tg-mgr-token').value.trim();
  const polling = document.getElementById('tg-mgr-polling').checked;

  TelegramManagerState.bot_token = token;
  TelegramManagerState.polling_enabled = polling;

  persistTelegramManagerConfig({
    bot_token: token,
    polling_enabled: polling
  }, 'Telegram Bot credentials saved successfully.');

  verifyTelegramBotToken(false);
}
window.saveTelegramBotCredentials = saveTelegramBotCredentials;

function renderTelegramChannelsList() {
  const container = document.getElementById('tg-channels-container');
  const badge = document.getElementById('tg-channel-count-badge');
  if (!container) return;

  const channels = TelegramManagerState.channels || [];
  if (badge) badge.textContent = `${channels.length} Channel${channels.length === 1 ? '' : 's'}`;

  if (channels.length === 0) {
    container.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 12px; border: 1px dashed var(--border-dim); border-radius: var(--radius-sm);">
        No destination channels linked yet.<br>
        <span style="font-size: 11px; opacity: 0.8;">Add your VIP Channel ID (e.g. <code>-100...</code>) or chat ID above.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = channels.map((ch, idx) => {
    const isEnabled = ch.enabled !== false;
    return `
      <div class="tg-channel-card">
        <div class="tg-channel-meta">
          <div class="tg-channel-title">
            <span>${escapeHtml(ch.title || 'Broadcast Channel')}</span>
            ${isEnabled ? '<span style="color: var(--emerald); font-size: 10px; font-weight: 700;">● Active</span>' : '<span style="color: var(--text-muted); font-size: 10px;">○ Muted</span>'}
          </div>
          <div class="tg-channel-id">${escapeHtml(ch.id)}</div>
        </div>
        <div class="tg-channel-actions">
          <label class="custom-switch" title="Toggle Channel Broadcast" style="display: flex; align-items: center; cursor: pointer;">
            <input type="checkbox" class="custom-checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleTelegramChannel('${escapeHtml(ch.id)}', this.checked)">
          </label>
          <button class="btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="testTelegramChannelPing('${escapeHtml(ch.id)}')" title="Send Test Ping">
            🔔 Ping
          </button>
          <button class="btn-secondary" style="padding: 4px 8px; font-size: 11px; color: var(--rose);" onclick="deleteTelegramChannel('${escapeHtml(ch.id)}')" title="Remove Channel">
            🗑️
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function addTelegramChannel() {
  const titleInput = document.getElementById('tg-new-channel-title');
  const idInput = document.getElementById('tg-new-channel-id');
  const title = titleInput ? titleInput.value.trim() : '';
  const id = idInput ? idInput.value.trim() : '';

  if (!id) {
    showToast('Please enter a valid Channel or Chat ID (e.g. -1001234567890)', 'error');
    return;
  }

  // Check duplicate
  if (TelegramManagerState.channels.some(c => c.id === id)) {
    showToast('This Channel ID is already added.', 'warning');
    return;
  }

  const newChannel = {
    id: id,
    title: title || `Channel ${TelegramManagerState.channels.length + 1}`,
    enabled: true
  };

  TelegramManagerState.channels.push(newChannel);
  if (titleInput) titleInput.value = '';
  if (idInput) idInput.value = '';

  renderTelegramChannelsList();
  updateBroadcastTargetSelector();

  persistTelegramManagerConfig({
    channels: TelegramManagerState.channels
  }, `Added destination channel: ${newChannel.title}`);
}
window.addTelegramChannel = addTelegramChannel;

function toggleTelegramChannel(channelId, enabled) {
  const ch = TelegramManagerState.channels.find(c => c.id === channelId);
  if (ch) {
    ch.enabled = enabled;
    renderTelegramChannelsList();
    persistTelegramManagerConfig({
      channels: TelegramManagerState.channels
    }, `${ch.title} ${enabled ? 'unmuted (active)' : 'muted'}.`);
  }
}
window.toggleTelegramChannel = toggleTelegramChannel;

function deleteTelegramChannel(channelId) {
  const ch = TelegramManagerState.channels.find(c => c.id === channelId);
  const title = ch ? ch.title : channelId;
  TelegramManagerState.channels = TelegramManagerState.channels.filter(c => c.id !== channelId);
  renderTelegramChannelsList();
  updateBroadcastTargetSelector();

  persistTelegramManagerConfig({
    channels: TelegramManagerState.channels
  }, `Removed channel: ${title}`);
}
window.deleteTelegramChannel = deleteTelegramChannel;

function testTelegramChannelPing(channelId) {
  showToast(`Sending test ping to ${channelId}...`, 'info');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.test_send_telegram_channel) {
    window.pywebview.api.test_send_telegram_channel(channelId).then(res => {
      if (res && res.success) {
        showToast('Test Ping successfully received on Telegram! 🔔', 'success');
      } else {
        showToast(`Test Ping failed: ${res && res.error ? res.error : 'Unknown error'}`, 'error');
      }
    }).catch(err => {
      showToast(`Error dispatching ping: ${err}`, 'error');
    });
  } else {
    showToast('Bridge API connecting...', 'info');
  }
}
window.testTelegramChannelPing = testTelegramChannelPing;

function updateBroadcastTargetSelector() {
  const select = document.getElementById('tg-broadcast-target-select');
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = '<option value="ALL">🌐 Broadcast to All Active Channels</option>';

  TelegramManagerState.channels.forEach(ch => {
    const opt = document.createElement('option');
    opt.value = ch.id;
    opt.textContent = `📢 ${ch.title} (${ch.id})${ch.enabled === false ? ' [Muted]' : ''}`;
    select.appendChild(opt);
  });

  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
    select.value = currentVal;
  }
}

function saveTelegramEventRules() {
  const rules = {
    signals: document.getElementById('tg-rule-signals')?.checked !== false,
    pre_signals: document.getElementById('tg-rule-pre-signals')?.checked !== false,
    outcomes: document.getElementById('tg-rule-outcomes')?.checked !== false,
    circuit_breaker: document.getElementById('tg-rule-circuit-breaker')?.checked !== false,
    news: document.getElementById('tg-rule-news')?.checked !== false,
    attach_charts: document.getElementById('tg-rule-charts')?.checked !== false,
    min_score: parseFloat(document.getElementById('tg-rule-min-score')?.value || 80),
    min_payout: parseFloat(document.getElementById('tg-rule-min-payout')?.value || 75)
  };

  TelegramManagerState.rules = rules;

  persistTelegramManagerConfig({
    rules: rules
  }, 'Event dispatch rules and signal thresholds saved.');
}
window.saveTelegramEventRules = saveTelegramEventRules;

// ----------------------------------------------------------------------------
// ----------------------------------------------------------------------------
// Message Template Customization & Live Preview Engine (Visual + Code Modes)
// ----------------------------------------------------------------------------
let currentTemplateEditorMode = 'visual';

function setTemplateEditorMode(mode) {
  currentTemplateEditorMode = mode;
  const visualBtn = document.getElementById('tg-mode-btn-visual');
  const codeBtn = document.getElementById('tg-mode-btn-code');
  const visualPane = document.getElementById('tg-visual-designer');
  const codePane = document.getElementById('tg-code-editor-container');

  if (mode === 'visual') {
    if (visualBtn) visualBtn.classList.add('active');
    if (codeBtn) codeBtn.classList.remove('active');
    if (visualPane) visualPane.style.display = 'block';
    if (codePane) codePane.style.display = 'none';

    const editor = document.getElementById('tg-template-editor');
    if (editor) {
      parseTemplateToVisualState(TelegramManagerState.activeTemplateKey, editor.value);
    }
  } else {
    if (visualBtn) visualBtn.classList.remove('active');
    if (codeBtn) codeBtn.classList.add('active');
    if (visualPane) visualPane.style.display = 'none';
    if (codePane) codePane.style.display = 'block';

    const editor = document.getElementById('tg-template-editor');
    if (editor) editor.focus();
  }
}
window.setTemplateEditorMode = setTemplateEditorMode;

function applyTelegramCardPreset(preset) {
  document.querySelectorAll('.tg-preset-chip').forEach(c => c.classList.remove('active'));
  const activeChip = document.getElementById(`tg-preset-${preset}`);
  if (activeChip) activeChip.classList.add('active');

  const setCheck = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.checked = val;
  };

  if (preset === 'vip') {
    setCheck('tg-vis-sig-header-toggle', true);
    setCheck('tg-vis-sig-asset', true);
    setCheck('tg-vis-sig-payout', true);
    setCheck('tg-vis-sig-direction', true);
    setCheck('tg-vis-sig-timeframe', true);
    setCheck('tg-vis-sig-entrytime', true);
    setCheck('tg-vis-sig-entryprice', true);
    setCheck('tg-vis-sig-expirytime', true);
    setCheck('tg-vis-sig-confluence', true);
    setCheck('tg-vis-sig-score', true);
    setCheck('tg-vis-sig-stake', true);
    setCheck('tg-vis-sig-ev', true);
    setCheck('tg-vis-sig-note-toggle', false);
    setCheck('tg-vis-sig-footer-toggle', true);
  } else if (preset === 'clean') {
    setCheck('tg-vis-sig-header-toggle', true);
    setCheck('tg-vis-sig-asset', true);
    setCheck('tg-vis-sig-payout', true);
    setCheck('tg-vis-sig-direction', true);
    setCheck('tg-vis-sig-timeframe', true);
    setCheck('tg-vis-sig-entrytime', true);
    setCheck('tg-vis-sig-entryprice', false);
    setCheck('tg-vis-sig-expirytime', false);
    setCheck('tg-vis-sig-confluence', false);
    setCheck('tg-vis-sig-score', true);
    setCheck('tg-vis-sig-stake', false);
    setCheck('tg-vis-sig-ev', false);
    setCheck('tg-vis-sig-note-toggle', false);
    setCheck('tg-vis-sig-footer-toggle', true);
  } else if (preset === 'pro') {
    setCheck('tg-vis-sig-header-toggle', true);
    setCheck('tg-vis-sig-asset', true);
    setCheck('tg-vis-sig-payout', true);
    setCheck('tg-vis-sig-direction', true);
    setCheck('tg-vis-sig-timeframe', true);
    setCheck('tg-vis-sig-entrytime', true);
    setCheck('tg-vis-sig-entryprice', true);
    setCheck('tg-vis-sig-expirytime', true);
    setCheck('tg-vis-sig-confluence', true);
    setCheck('tg-vis-sig-score', true);
    setCheck('tg-vis-sig-stake', true);
    setCheck('tg-vis-sig-ev', true);
    setCheck('tg-vis-sig-note-toggle', true);
    setCheck('tg-vis-sig-footer-toggle', true);
  } else if (preset === 'compact') {
    setCheck('tg-vis-sig-header-toggle', true);
    setCheck('tg-vis-sig-asset', true);
    setCheck('tg-vis-sig-payout', true);
    setCheck('tg-vis-sig-direction', true);
    setCheck('tg-vis-sig-timeframe', true);
    setCheck('tg-vis-sig-entrytime', true);
    setCheck('tg-vis-sig-entryprice', false);
    setCheck('tg-vis-sig-expirytime', false);
    setCheck('tg-vis-sig-confluence', false);
    setCheck('tg-vis-sig-score', false);
    setCheck('tg-vis-sig-stake', false);
    setCheck('tg-vis-sig-ev', false);
    setCheck('tg-vis-sig-note-toggle', false);
    setCheck('tg-vis-sig-footer-toggle', false);
  }

  onVisualDesignerChange();
}
window.applyTelegramCardPreset = applyTelegramCardPreset;

function onVisualDesignerChange() {
  const key = TelegramManagerState.activeTemplateKey;
  let generated = '';

  const isChecked = id => !!document.getElementById(id)?.checked;
  const getVal = (id, fallback) => document.getElementById(id)?.value?.trim() || fallback;

  if (key === 'signal') {
    const showHeader = isChecked('tg-vis-sig-header-toggle');
    const headerTitle = getVal('tg-vis-sig-header-text', 'SIGNAL ALERT: {strategy}');
    if (showHeader) {
      generated += `🚀 <b>${headerTitle}</b>\n────────────────────────\n`;
    }
    if (isChecked('tg-vis-sig-asset')) {
      generated += `📊 <b>Asset:</b> <code>{asset}</code>\n`;
    }
    if (isChecked('tg-vis-sig-payout')) {
      generated += `💰 <b>OTC Payout:</b> <b>{payout}%</b>\n`;
    }
    if (isChecked('tg-vis-sig-direction')) {
      generated += `{arrow} <b>Direction:</b> <b>{direction}</b>\n`;
    }
    if (isChecked('tg-vis-sig-timeframe')) {
      generated += `⏱ <b>Timeframe:</b> <b>{timeframe}</b>\n⏳ <b>Expiry Duration:</b> <b>{expiry} Mins</b>\n`;
    }
    if (isChecked('tg-vis-sig-entrytime')) {
      generated += `🕒 <b>Entry Time:</b> <b>Next Candle Open (00s) | {entry_time} IST</b>\n`;
    }
    if (isChecked('tg-vis-sig-entryprice')) {
      generated += `💵 <b>Entry Price:</b> <code>{entry_price}</code>\n`;
    }

    const hasIntel = isChecked('tg-vis-sig-confluence') || isChecked('tg-vis-sig-score') || isChecked('tg-vis-sig-stake') || isChecked('tg-vis-sig-ev') || isChecked('tg-vis-sig-expirytime');
    if (hasIntel) {
      generated += `━━━━━━━━━━━━━━━━━━━━\n`;
      if (isChecked('tg-vis-sig-confluence')) {
        generated += `{confluence_section}`;
      }
      if (isChecked('tg-vis-sig-score')) {
        generated += `🎯 <b>Setup Quality Score:</b> <b>{confidence}% ({tier})</b>\n`;
      }
      if (isChecked('tg-vis-sig-stake')) {
        generated += `{stake_line}`;
      }
      if (isChecked('tg-vis-sig-ev')) {
        generated += `{ev_line}`;
      }
      if (isChecked('tg-vis-sig-expirytime')) {
        generated += `⏰ <b>Expiry Target:</b> <b>{expiry_time} IST</b>\n`;
      }
    }

    if (isChecked('tg-vis-sig-note-toggle')) {
      const note = getVal('tg-vis-sig-note-text', '');
      if (note) {
        generated += `────────────────────────\n📢 <i>${note}</i>\n`;
      }
    }

    if (isChecked('tg-vis-sig-footer-toggle')) {
      const footer = getVal('tg-vis-sig-footer-text', 'TradePulse VIP Institutional Signal');
      generated += `🔒 <i>${footer}</i>`;
    }
  } else if (key === 'pre_signal') {
    const h = getVal('tg-vis-pre-header-text', 'PRE-SIGNAL RADAR: PREPARE ENTRY');
    generated += `⚡ <b>${h}</b>\n────────────────────────\n`;
    if (isChecked('tg-vis-pre-asset')) generated += `📊 <b>Asset:</b> <code>{asset}</code>\n`;
    if (isChecked('tg-vis-pre-direction')) generated += `🎯 <b>Direction:</b> <b>{dir_badge}</b>\n`;
    if (isChecked('tg-vis-pre-timeframe')) generated += `⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry}m)\n`;
    if (isChecked('tg-vis-pre-payout')) generated += `💰 <b>Payout:</b> <b>{payout}%</b>\n`;
    if (isChecked('tg-vis-pre-seconds')) generated += `⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n`;
    if (isChecked('tg-vis-pre-pattern')) generated += `🧠 <b>Forming Pattern:</b> {strategy}\n`;
    if (isChecked('tg-vis-pre-stake')) generated += `{stake_line}`;
    generated += `────────────────────────\n`;
    const f = getVal('tg-vis-pre-footer-text', 'Prepare pair & stake in Quotex. Official entry fires on candle close.');
    generated += `<i>${f}</i>`;
  } else if (key === 'outcome') {
    generated += `{header}\n────────────────────────\n`;
    if (isChecked('tg-vis-out-asset')) generated += `📊 <b>Asset:</b> <code>{asset}</code>\n`;
    if (isChecked('tg-vis-out-strategy')) generated += `🎯 <b>Strategy:</b> <code>{strategy}</code>\n`;
    if (isChecked('tg-vis-out-direction')) generated += `📌 <b>Direction:</b> <b>{direction}</b>\n`;
    if (isChecked('tg-vis-out-badge')) generated += `🏁 <b>Result:</b> <b>{outcome_badge}</b>\n`;
    if (isChecked('tg-vis-out-prices')) generated += `━━━━━━━━━━━━━━━━━━━━\n💵 <b>Entry Strike:</b> <code>{entry_price}</code>\n🏁 <b>Exit Price:</b>   <code>{exit_price}</code>\n`;
    if (isChecked('tg-vis-out-profit')) generated += `{pnl_text}\n`;
    generated += `━━━━━━━━━━━━━━━━━━━━\n`;
    const f = getVal('tg-vis-out-footer-text', 'TradePulse 24/7 Real-Time Outcome Verification');
    generated += `🔒 <i>${f}</i>`;
  } else if (key === 'circuit_breaker') {
    const h = getVal('tg-vis-cb-header-text', 'TRADEPULSE CIRCUIT BREAKER ACTIVATED');
    generated += `🛑 <b>${h}</b>\n━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>Signal Scanner Auto-Paused</b>\n`;
    if (isChecked('tg-vis-cb-reason')) generated += `• <b>Trigger Reason:</b> <b>{cb_reason}</b>\n`;
    if (isChecked('tg-vis-cb-pnl')) generated += `• <b>Session Net PnL:</b> <b>{net_pnl}</b>\n`;
    if (isChecked('tg-vis-cb-trades')) generated += `• <b>Total Trades:</b> <b>{total_trades}</b>\n`;
    generated += `━━━━━━━━━━━━━━━━━━━━\n🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>`;
  }

  // Update in-memory template and code editor textarea
  TelegramManagerState.templates[key] = generated;
  const editor = document.getElementById('tg-template-editor');
  if (editor) {
    editor.value = generated;
    const counter = document.getElementById('tg-template-char-count');
    if (counter) counter.textContent = `${generated.length} chars`;
  }

  renderTelegramLivePreview(key, generated);
}
window.onVisualDesignerChange = onVisualDesignerChange;

function parseTemplateToVisualState(key, text) {
  // Show only field section corresponding to the active template
  ['signal', 'pre_signal', 'outcome', 'circuit_breaker'].forEach(k => {
    const el = document.getElementById(`tg-visual-fields-${k}`);
    if (el) el.style.display = (k === key) ? 'block' : 'none';
  });

  const setCheck = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.checked = val;
  };
  const content = text || '';

  if (key === 'signal') {
    setCheck('tg-vis-sig-header-toggle', content.includes('SIGNAL ALERT') || content.includes('🚀') || content.includes('<b>'));
    setCheck('tg-vis-sig-asset', content.includes('{asset}'));
    setCheck('tg-vis-sig-payout', content.includes('{payout}'));
    setCheck('tg-vis-sig-direction', content.includes('{direction}'));
    setCheck('tg-vis-sig-timeframe', content.includes('{timeframe}'));
    setCheck('tg-vis-sig-entrytime', content.includes('{entry_time}'));
    setCheck('tg-vis-sig-entryprice', content.includes('{entry_price}'));
    setCheck('tg-vis-sig-expirytime', content.includes('{expiry_time}'));
    setCheck('tg-vis-sig-confluence', content.includes('{confluence_section}'));
    setCheck('tg-vis-sig-score', content.includes('{confidence}'));
    setCheck('tg-vis-sig-stake', content.includes('{stake_line}') || content.includes('{rec_stake}'));
    setCheck('tg-vis-sig-ev', content.includes('{ev_line}') || content.includes('{ev_edge}'));
    setCheck('tg-vis-sig-note-toggle', content.includes('📢'));
    setCheck('tg-vis-sig-footer-toggle', content.includes('<i>') || content.includes('TradePulse'));
  } else if (key === 'pre_signal') {
    setCheck('tg-vis-pre-asset', content.includes('{asset}'));
    setCheck('tg-vis-pre-direction', content.includes('{dir_badge}') || content.includes('{direction}'));
    setCheck('tg-vis-pre-timeframe', content.includes('{timeframe}'));
    setCheck('tg-vis-pre-payout', content.includes('{payout}'));
    setCheck('tg-vis-pre-seconds', content.includes('{remaining_seconds}'));
    setCheck('tg-vis-pre-pattern', content.includes('{strategy}'));
    setCheck('tg-vis-pre-stake', content.includes('{stake_line}') || content.includes('{rec_stake}'));
  } else if (key === 'outcome') {
    setCheck('tg-vis-out-asset', content.includes('{asset}'));
    setCheck('tg-vis-out-strategy', content.includes('{strategy}'));
    setCheck('tg-vis-out-direction', content.includes('{direction}'));
    setCheck('tg-vis-out-badge', content.includes('{outcome_badge}'));
    setCheck('tg-vis-out-prices', content.includes('{entry_price}') || content.includes('{exit_price}'));
    setCheck('tg-vis-out-profit', content.includes('{pnl_text}'));
  } else if (key === 'circuit_breaker') {
    setCheck('tg-vis-cb-reason', content.includes('{cb_reason}'));
    setCheck('tg-vis-cb-pnl', content.includes('{net_pnl}'));
    setCheck('tg-vis-cb-trades', content.includes('{total_trades}'));
  }
}

function onSelectTelegramTemplate(key) {
  // Sync previous editor changes before switching
  const prevKey = TelegramManagerState.activeTemplateKey;
  const editor = document.getElementById('tg-template-editor');
  if (prevKey && prevKey !== key && editor && currentTemplateEditorMode === 'code') {
    TelegramManagerState.templates[prevKey] = editor.value;
  }

  TelegramManagerState.activeTemplateKey = key;
  const selector = document.getElementById('tg-template-selector');
  if (selector) selector.value = key;

  // 1. Populate dynamic token palette
  const palette = document.getElementById('tg-token-palette');
  const tokens = TG_TEMPLATE_TOKENS[key] || [];
  if (palette) {
    palette.innerHTML = tokens.map(t => `
      <span class="tg-token-pill" onclick="insertTokenAtCursor('${t.token}')" title="${escapeHtml(t.desc)}">
        ${t.token}
      </span>
    `).join('');
  }

  // 2. Load template text (with default fallback)
  const templateText = TelegramManagerState.templates[key] || DEFAULT_TELEGRAM_TEMPLATES[key] || '';
  TelegramManagerState.templates[key] = templateText;
  if (editor) {
    editor.value = templateText;
    const counter = document.getElementById('tg-template-char-count');
    if (counter) counter.textContent = `${templateText.length} chars`;
  }

  // 3. Update Visual Designer state to match active template
  parseTemplateToVisualState(key, templateText);

  // 4. Render live preview
  renderTelegramLivePreview(key, templateText);
}
window.onSelectTelegramTemplate = onSelectTelegramTemplate;

function insertTokenAtCursor(token) {
  const editor = document.getElementById('tg-template-editor');
  if (!editor) return;

  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const text = editor.value;

  editor.value = text.substring(0, start) + token + text.substring(end);
  editor.selectionStart = editor.selectionEnd = start + token.length;
  editor.focus();

  onTelegramTemplateInput();
}
window.insertTokenAtCursor = insertTokenAtCursor;

function onTelegramTemplateInput() {
  const editor = document.getElementById('tg-template-editor');
  const counter = document.getElementById('tg-template-char-count');
  if (!editor) return;

  const val = editor.value;
  if (counter) counter.textContent = `${val.length} chars`;

  renderTelegramLivePreview(TelegramManagerState.activeTemplateKey, val);
}
window.onTelegramTemplateInput = onTelegramTemplateInput;

function renderTelegramLivePreview(key, templateText) {
  const previewBody = document.getElementById('tg-preview-body');
  if (!previewBody) return;

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  const timeEl = document.getElementById('tg-preview-time');
  if (timeEl) timeEl.textContent = timeStr;

  const buttonsContainer = document.getElementById('tg-preview-buttons');
  if (buttonsContainer) {
    if (key === 'signal' || key === 'pre_signal') {
      buttonsContainer.style.display = 'flex';
      buttonsContainer.innerHTML = '<div class="tg-preview-btn">📈 Trade on Quotex</div>';
    } else {
      buttonsContainer.style.display = 'none';
    }
  }

  // Check if PyWebView API is ready to render server-side
  if (window.pywebview && window.pywebview.api && window.pywebview.api.preview_telegram_template) {
    window.pywebview.api.preview_telegram_template(key, templateText).then(res => {
      if (res && res.success && res.rendered) {
        previewBody.innerHTML = res.rendered.replace(/\n/g, '<br>');
      } else {
        renderClientSidePreview(key, templateText);
      }
    }).catch(() => {
      renderClientSidePreview(key, templateText);
    });
  } else {
    renderClientSidePreview(key, templateText);
  }
}

function renderClientSidePreview(key, templateText) {
  const previewBody = document.getElementById('tg-preview-body');
  if (!previewBody) return;

  const now = new Date();
  const istTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:00 IST`;
  const nextMin = new Date(now.getTime() + 60000);
  const expiryTime = `${String(nextMin.getHours()).padStart(2, '0')}:${String(nextMin.getMinutes()).padStart(2, '0')}:00 IST`;

  const mockContext = {
    '{asset}': 'EUR/USD (OTC)',
    '{direction}': 'CALL (UP) 🟢',
    '{dir_badge}': 'CALL (UP) 🟢',
    '{arrow}': '📈',
    '{payout}': '92%',
    '{confidence}': '94',
    '{tier}': 'MAX CONFLUENCE',
    '{strategy}': 'Engulfing Breakout Momentum',
    '{timeframe}': '1M',
    '{duration}': '1',
    '{expiry}': '1',
    '{expiry_minutes}': '1',
    '{entry_time}': istTime,
    '{expiry_time}': expiryTime,
    '{entry_price}': '1.08542',
    '{exit_price}': '1.08560',
    '{rec_stake}': '$25.00',
    '{stake_line}': '💰 <b>Recommended Stake:</b> <b>$25.00 (Step 1)</b>\n',
    '{martingale_step}': '1',
    '{ev_edge}': '+$8.28',
    '{ev_line}': '🧮 <b>Quant Edge:</b> <b>EV +$8.28</b>\n',
    '{confluence_section}': '🤝 <b>Confirming:</b> <b>MTF Trend + RSI Oversold</b>\n',
    '{status}': 'WIN',
    '{outcome_badge}': 'WIN ✅',
    '{pnl_text}': '💰 <b>Profit:</b> <b>+92% Return</b>',
    '{remaining_seconds}': '18',
    '{cb_reason}': 'Daily Max Loss Limit Hit (-$150.00)',
    '{net_pnl}': '-$152.50',
    '{win_rate}': '54.2%',
    '{total_trades}': '24',
    '{header}': key === 'signal' ? '⚡ <b>VIP SIGNAL ALERT</b>' : '⚡ <b>PRE-SIGNAL RADAR</b>'
  };

  let rendered = templateText || '';
  for (const [token, val] of Object.entries(mockContext)) {
    rendered = rendered.split(token).join(val);
  }

  // Convert line breaks to <br> for HTML chat bubble preview
  previewBody.innerHTML = rendered.replace(/\n/g, '<br>');
}

function sendTestPreviewToChannel() {
  const key = TelegramManagerState.activeTemplateKey;
  const editor = document.getElementById('tg-template-editor');
  const templateText = editor ? editor.value : (TelegramManagerState.templates[key] || '');

  if (!templateText) {
    showToast('Template is empty.', 'error');
    return;
  }

  showToast('Sending live test preview to Telegram channel...', 'info');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.send_test_rendered_template) {
    window.pywebview.api.send_test_rendered_template(key, templateText).then(res => {
      if (res && res.success) {
        showToast(res.message || 'Test card successfully sent to Telegram! 📱', 'success');
      } else {
        showToast(`Failed to send test: ${res?.error || 'Unknown error'}`, 'error');
      }
    }).catch(err => {
      showToast(`Error dispatching test: ${err}`, 'error');
    });
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.test_telegram) {
    window.pywebview.api.test_telegram().then(ok => {
      if (ok) showToast('Test alert sent to Telegram!', 'success');
      else showToast('Could not send test. Verify bot token & channel ID.', 'error');
    });
  } else {
    showToast('Backend API not connected.', 'error');
  }
}
window.sendTestPreviewToChannel = sendTestPreviewToChannel;

function saveActiveTelegramTemplate() {
  const key = TelegramManagerState.activeTemplateKey || 'signal';
  const editor = document.getElementById('tg-template-editor');

  if (currentTemplateEditorMode === 'visual') {
    onVisualDesignerChange();
  } else if (editor) {
    TelegramManagerState.templates[key] = editor.value;
  }

  const content = TelegramManagerState.templates[key] || (editor ? editor.value : '');
  if (!content || !content.trim()) {
    showToast('Template content cannot be empty.', 'error');
    return;
  }

  const trimmedContent = content.trim();
  TelegramManagerState.templates[key] = trimmedContent;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_telegram_template) {
    window.pywebview.api.save_telegram_template(key, trimmedContent).then(res => {
      if (res && res.success) {
        if (res.config && res.config.templates) {
          TelegramManagerState.templates = { ...TelegramManagerState.templates, ...res.config.templates };
        } else if (res.template) {
          TelegramManagerState.templates[key] = res.template;
        }
        showToast(`Custom ${key.toUpperCase()} template saved successfully! 💾`, 'success');
      } else {
        showToast(`Failed to save template: ${res?.error || 'Unknown error'}`, 'error');
      }
    }).catch(err => {
      showToast(`Save error: ${err}`, 'error');
    });
  } else {
    persistTelegramManagerConfig({
      templates: TelegramManagerState.templates
    }, `Custom ${key.toUpperCase()} template saved successfully! 💾`);
  }
}
window.saveActiveTelegramTemplate = saveActiveTelegramTemplate;

function resetActiveTelegramTemplate() {
  const key = TelegramManagerState.activeTemplateKey || 'signal';
  if (!confirm(`Reset ${key.toUpperCase()} template back to official default?`)) return;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.reset_telegram_template) {
    window.pywebview.api.reset_telegram_template(key).then(res => {
      if (res && res.success) {
        TelegramManagerState.templates[key] = res.template;
        const editor = document.getElementById('tg-template-editor');
        if (editor) editor.value = res.template;
        parseTemplateToVisualState(key, res.template);
        onTelegramTemplateInput();
        showToast(`Template for ${key} reset to default.`, 'info');
      }
    });
  }
}
window.resetActiveTelegramTemplate = resetActiveTelegramTemplate;

function sendCustomTelegramAnnouncement() {
  const targetSelect = document.getElementById('tg-broadcast-target-select');
  const textArea = document.getElementById('tg-broadcast-text');
  const feedback = document.getElementById('tg-broadcast-feedback');

  const targetId = targetSelect ? targetSelect.value : 'ALL';
  const text = textArea ? textArea.value.trim() : '';

  if (!text) {
    showToast('Announcement message cannot be empty.', 'error');
    return;
  }

  if (feedback) {
    feedback.textContent = '🚀 Dispatching announcement...';
    feedback.style.color = 'var(--cyan-bright)';
  }

  const destination = targetId === 'ALL' ? null : targetId;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.broadcast_custom_telegram_message) {
    window.pywebview.api.broadcast_custom_telegram_message(text, destination).then(res => {
      if (res && res.success) {
        showToast('Announcement broadcast successfully dispatched! 📣', 'success');
        if (textArea) textArea.value = '';
        if (feedback) {
          feedback.textContent = `✓ Dispatched to ${res.sent_count || 1} channel(s)`;
          feedback.style.color = 'var(--emerald)';
          setTimeout(() => { if (feedback) feedback.textContent = ''; }, 4000);
        }
      } else {
        showToast(`Broadcast failed: ${res && res.error ? res.error : 'Unknown error'}`, 'error');
        if (feedback) {
          feedback.textContent = '✕ Dispatch failed';
          feedback.style.color = 'var(--rose)';
        }
      }
    }).catch(err => {
      showToast(`Broadcast request error: ${err}`, 'error');
    });
  }
}
window.sendCustomTelegramAnnouncement = sendCustomTelegramAnnouncement;

function refreshTelegramManagerState() {
  showToast('Refreshing Telegram state...', 'info');
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_telegram_manager_state) {
    window.pywebview.api.get_telegram_manager_state().then(state => {
      initTelegramManagerState(state);
      showToast('Telegram Manager state synchronized.', 'success');
    });
  }
}
window.refreshTelegramManagerState = refreshTelegramManagerState;

function persistTelegramManagerConfig(patch, successMsg) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.update_telegram_manager_config) {
    window.pywebview.api.update_telegram_manager_config(patch).then(res => {
      if (res && res.success) {
        if (res.config) {
          initTelegramManagerState(res.config);
        }
        if (successMsg) showToast(successMsg, 'success');
      } else {
        showToast('Error saving Telegram configuration: ' + (res?.error || 'Unknown error'), 'error');
      }
    }).catch(err => {
      showToast(`Save error: ${err}`, 'error');
    });
  } else {
    showToast('Telegram configuration updated locally.', 'info');
  }
}
