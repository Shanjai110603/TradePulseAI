"""
TradePulse Main Entrypoint — Dual-Mode Runtime
==============================================
Runs either as a standalone native Desktop Application (with modern PyWebView GUI)
or as a 24/7 Headless Background Daemon for cloud VPS hosting.

Usage:
  python main.py             # Desktop GUI Mode (Windows / Mac / Linux desktop)
  python main.py --headless  # 24/7 Headless VPS Daemon Mode (Ubuntu / Debian / Docker)
"""
import argparse
import asyncio
import json
import logging
import os
import platform
import queue
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure WebView2 runs without overscroll rubber-banding, frame blocks, or GPU watchdog crashes
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-features=ElasticOverscroll --disable-web-security --allow-running-insecure-content --disable-gpu-watchdog'

from core.charts.generator import ChartGenerator
from core.config import settings
from core.indicators.engine import TechnicalIndicatorEngine
from core.ingester.asset_registry import asset_registry, REGISTERED_ASSETS
from core.ingester.auth_manager import auth_manager
from core.ingester.socket_client import QuotexSocketClient
from core.models.candle import Candle, CandleStore
from core.models.signal import Signal
from core.storage.db import db
from core.strategy.backtest import HistoricalBacktestEngine
from core.strategy.compiler import StrategyCompiler
from core.strategy.confluence import ConfluenceEngine
from core.strategy.cooldown import cooldown_manager
from core.strategy.manager import strategy_manager
from core.strategy.rules_ast import PatternRuleEngine
from core.strategy.tracker import SignalTracker
from core.telegram.bridge import TelegramBridge
from core.telegram.formatter import TelegramFormatter
from core.telegram.manager import TelegramManager
from core.ingester.real_market_feed import RealMarketFeed
from core.webhooks.server import WebhookServer
from core.news.calendar import EconomicCalendarEngine
from core.strategy.quant_ev import QuantEVFilter
from core.strategy.risk_manager import RiskManager
from core.strategy.session_scheduler import SessionScheduler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TradePulse")

# Setup persistent rotating file logger in user data directory
try:
    from logging.handlers import RotatingFileHandler
    log_file = settings.resolved_data_dir / "tradepulse.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(str(log_file), maxBytes=10*1024*1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(file_handler)
except Exception:
    pass


_single_instance_mutex = None

def ensure_single_instance():
    """Ensures only a single instance of TradePulse runs, avoiding WebView2 profile lock collisions."""
    global _single_instance_mutex
    if sys.platform == "win32":
        try:
            import ctypes
            ERROR_ALREADY_EXISTS = 183
            _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\TradePulse_SingleInstance_Mutex")
            if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                logger.warning("[STARTUP] Another TradePulse instance is running. Cleaning stale instances...")
                try:
                    import psutil
                    current_pid = os.getpid()
                    parent_pid = os.getppid()
                    for p in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if p.pid in (current_pid, parent_pid):
                                continue
                            p_name = (p.info.get('name') or '').lower()
                            p_exe = (p.info.get('exe') or '').lower()
                            if 'tradepulse' in p_name or 'tradepulse' in p_exe:
                                logger.warning(f"[STARTUP] Terminating stale TradePulse process (PID {p.pid})...")
                                p.kill()
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[STARTUP] Mutex check note: {e}")


class TradePulseEngine:
    """Core coordinator orchestrating market data ingestion, strategy evaluation, and alert dispatching."""

    def __init__(self):
        self.candle_store = CandleStore(max_bars=120)
        self.session_token = auth_manager.get_valid_session_token()
        self.start_time = time.time()
        self.running = False
        self.scanning_paused = False
        self.unwatched_symbols = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._webview_window = None
        self._bridge_api = None
        self.ui_ready: bool = False
        self._eval_pending: bool = False
        self._pre_signal_min: Dict[str, int] = {}

        # Real-time UI tick & payout batch buffer (prevents WinForms COM flooding)
        self._tick_buffer: Dict[str, Any] = {}
        self._payout_buffer: Dict[str, float] = {}
        self._buffer_lock = threading.Lock()
        self._flush_thread: Optional[threading.Thread] = None

        # Subsystems
        self.telegram_manager = TelegramManager()
        self.tracker = SignalTracker(
            self.candle_store,
            on_outcome_callback=self._on_trade_outcome,
            sequential_trade_lock=self.telegram_manager.sequential_trade_lock,
            loss_cooldown_seconds=self.telegram_manager.loss_cooldown_seconds
        )
        self.telegram = TelegramBridge(on_command_callback=self._on_telegram_command, manager=self.telegram_manager)
        self.webhook_server = WebhookServer(port=8765, on_signal_callback=self._on_external_webhook)
        self.news_calendar = EconomicCalendarEngine(data_dir=settings.resolved_data_dir)
        self.quant_ev = QuantEVFilter()
        self.risk_manager = RiskManager()
        self.scheduler = SessionScheduler()
        self.ws_client = QuotexSocketClient(
            candle_store=self.candle_store,
            session_token=self.session_token,
            on_tick_callback=self._on_tick,
            on_candle_callback=self._on_candle_completed,
            on_status_callback=self._on_status_update
        )
        # Dedicated Open-Source Real Market Feed (Forex, Commodities, Binance Spot Crypto)
        self.real_market_feed = RealMarketFeed(
            candle_store=self.candle_store,
            on_tick=self._on_tick,
            on_candle=self._on_candle_completed
        )
        # Register real-time payout listener
        asset_registry.add_payout_callback(self._on_payout_updated)

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_webview_window(self, window):
        self._webview_window = window

    def set_bridge_api(self, api):
        self._bridge_api = api

    def safe_emit_js(self, js: str):
        """Dispatches JavaScript execution safely and asynchronously without blocking or deadlocks."""
        if not getattr(self, "ui_ready", False):
            return
        emitted = False
        try:
            form = None
            if self._bridge_api:
                form = self._bridge_api._main_form
                if not form and self._bridge_api._main_win:
                    try:
                        from webview.platforms.winforms import BrowserView
                        form = BrowserView.instances.get(self._bridge_api._main_win.uid)
                        self._bridge_api._main_form = form
                    except Exception:
                        pass

            if form and not getattr(form, 'IsDisposed', False):
                Action = (self._bridge_api and self._bridge_api._Action) or __import__('System', fromlist=['Action']).Action
                if hasattr(form, 'browser') and hasattr(form.browser, 'webview'):
                    wv = form.browser.webview
                    def do_exec():
                        try:
                            core_wv = None
                            try:
                                core_wv = getattr(wv, "CoreWebView2", None)
                            except Exception:
                                pass
                            if core_wv:
                                core_wv.ExecuteScriptAsync(js)
                            elif hasattr(wv, 'ExecuteScriptAsync'):
                                wv.ExecuteScriptAsync(js)
                        except Exception as e:
                            logger.debug(f"[SAFE_EMIT] ExecuteScriptAsync note: {e}")
                    if hasattr(form, 'InvokeRequired') and form.InvokeRequired:
                        form.BeginInvoke(Action(do_exec))
                    else:
                        do_exec()
                    emitted = True
        except Exception as ex:
            logger.debug(f"[SAFE_EMIT] WinForms dispatch note: {ex}")

        # Fallback to pywebview evaluate_js only if UI is confirmed ready and not already pending
        if not emitted and self._webview_window and getattr(self, "ui_ready", False):
            if not getattr(self, '_eval_pending', False):
                self._eval_pending = True
                def async_eval():
                    try:
                        self._webview_window.evaluate_js(js)
                    except Exception as we:
                        logger.debug(f"[SAFE_EMIT] evaluate_js fallback note: {we}")
                    finally:
                        self._eval_pending = False
                threading.Thread(target=async_eval, daemon=True).start()

    def start(self):
        self.running = True
        self._flush_thread = threading.Thread(target=self._ui_flush_loop, daemon=True, name="TradePulse-UIFlush")
        self._flush_thread.start()
        self.ws_client.start()
        self.real_market_feed.start()
        self.tracker.start()
        self.telegram.start()
        self.webhook_server.start()
        logger.info("[ENGINE] TradePulse Core Engine online (Quotex OTC + Open-Source Real Market feeds active)!")

    def stop(self):
        self.running = False
        self.ws_client.stop()
        self.real_market_feed.stop()
        self.tracker.stop()
        self.telegram.stop()
        self.webhook_server.stop()
        logger.info("[ENGINE] TradePulse Core Engine stopped.")

    def _ui_flush_loop(self):
        """Flushes buffered price ticks and payout updates to the UI smoothly at ~12 FPS."""
        while self.running:
            time.sleep(0.08)
            if not getattr(self, "ui_ready", False):
                continue
            ticks = None
            payouts = None
            with self._buffer_lock:
                if self._tick_buffer:
                    ticks = self._tick_buffer
                    self._tick_buffer = {}
                if self._payout_buffer:
                    payouts = self._payout_buffer
                    self._payout_buffer = {}

            if ticks:
                try:
                    js_ticks = json.dumps(ticks)
                    self.safe_emit_js(f"if(window.onBatchTicks) window.onBatchTicks({js_ticks});")
                except Exception:
                    pass

            if payouts:
                try:
                    js_payouts = json.dumps(payouts)
                    self.safe_emit_js(f"if(window.onBatchPayouts) window.onBatchPayouts({js_payouts});")
                except Exception:
                    pass

    def restart_ingestion(self):
        """Safely restarts the WebSocket client on the engine background async loop."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_restart_ws(), self._loop)
        else:
            logger.warning("[ENGINE] Async background event loop not running.")

    async def _async_restart_ws(self):
        logger.info("[ENGINE] Reconnecting WebSocket client with authentic broker cookies...")
        self.ws_client.stop()
        await asyncio.sleep(0.5)
        self.ws_client.start()

    def _on_payout_updated(self, symbol: str, payout: float):
        """Called whenever an authentic live broker payout percentage is received."""
        with self._buffer_lock:
            self._payout_buffer[symbol] = payout

    # -------------------------------------------------------------------------
    # Ingestion Callbacks
    # -------------------------------------------------------------------------

    def _on_tick(self, symbol: str, price: float, source: str = "ws_subscription"):
        """Called whenever a genuine real-time price tick arrives."""
        with self._buffer_lock:
            self._tick_buffer[symbol] = {"price": price, "source": source}
        now = time.time()
        if not hasattr(self, '_last_logged_tick_ts'):
            self._last_logged_tick_ts = {}
        if now - self._last_logged_tick_ts.get(symbol, 0.0) > 5.0:
            self._last_logged_tick_ts[symbol] = now
            logger.info(f"[LIVE TICK] {symbol} @ {price} (source={source})")

        # Early Warning / Pre-Signal Radar hook (triggers ~15s before candle close)
        sec_of_min = int(now) % 60
        if getattr(settings, "PRE_ALERTS_ENABLED", True) and 45 <= sec_of_min <= 52:
            current_min_ts = int(now // 60) * 60
            if self._pre_signal_min.get(symbol) != current_min_ts:
                self._pre_signal_min[symbol] = current_min_ts
                if self._loop and self._loop.is_running() and self.running and not self.scanning_paused and symbol not in self.unwatched_symbols:
                    session_ok, _ = self.scheduler.is_session_active(now)
                    news_blocked, _ = self.news_calendar.is_in_blackout(symbol, now)
                    cb_halted, _ = self.risk_manager.check_circuit_breaker()
                    if session_ok and not news_blocked and not cb_halted:
                        asyncio.run_coroutine_threadsafe(
                            self._evaluate_pre_signal(symbol, price, max(5, 60 - sec_of_min)),
                            self._loop
                        )

    async def _evaluate_pre_signal(self, symbol: str, current_price: float, remaining_seconds: int):
        """Evaluates forming bar at second 45-52 for early manual entry preparation."""
        try:
            # Check sequential trade lock and cooldown before evaluating pre-alerts
            can_fire, lock_reason = self.tracker.can_dispatch_signal()
            if not can_fire:
                logger.debug(f"[PRE-SIGNAL LOCKED] {symbol} skipped: {lock_reason}")
                return

            candles_1m = self.candle_store.get_candles(symbol, "1M")
            if len(candles_1m) < 15:
                return

            payout = asset_registry.get_payout(symbol)
            is_otc = "(OTC)" in symbol or "_otc" in symbol.lower()
            if getattr(settings, "OTC_FLATLINE_GUARD", True) and is_otc:
                snapshot_1m = TechnicalIndicatorEngine.calculate_technical_snapshot(candles_1m)
                if snapshot_1m and snapshot_1m.get("is_flatlined"):
                    return

            prev_candle = candles_1m[-1]
            tentative_open = prev_candle.close
            tentative_high = max(tentative_open, current_price)
            tentative_low = min(tentative_open, current_price)
            tentative_candle = Candle(
                open=tentative_open,
                high=tentative_high,
                low=tentative_low,
                close=current_price,
                volume=10,
                timestamp=int(time.time())
            )
            eval_candles = candles_1m + [tentative_candle]
            eval_snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(eval_candles)
            candles_5m = self.candle_store.get_candles(symbol, "5M")
            candles_15m = self.candle_store.get_candles(symbol, "15M")
            mtf_dict = {
                "1M": eval_candles,
                "3M": self.candle_store.get_candles(symbol, "3M"),
                "5M": candles_5m,
                "15M": candles_15m
            }

            active_strategies = strategy_manager.get_active_strategies()
            for strat in active_strategies:
                if (strat.timeframe or "1M").upper() != "1M":
                    continue
                if payout is not None and payout < strat.min_payout:
                    continue

                scope = strat.assets or ["ALL_MARKETS"]
                in_scope = "ALL_MARKETS" in scope or "ALL" in scope or ("ALL_OTC" in scope and is_otc) or symbol in scope
                if not in_scope:
                    continue

                compiled_ast = StrategyCompiler.compile_strategy_ast(strat)
                directions = ["CALL", "PUT"] if strat.direction == "BOTH" else [strat.direction]
                for direction in directions:
                    passed, _, _ = PatternRuleEngine.evaluate_node(
                        compiled_ast,
                        eval_candles,
                        multi_timeframe_candles=mtf_dict,
                        technical_snapshot=eval_snapshot,
                        direction_context=direction
                    )
                    if passed:
                        ev_res = self.quant_ev.evaluate_edge(symbol, payout or 85.0, confidence_score=65.0)
                        if not ev_res["passed"]:
                            return
                        rec_pos = self.risk_manager.get_recommended_stake()
                        pre_data = {
                            "symbol": symbol,
                            "direction": direction,
                            "strategy_name": strat.name,
                            "timeframe": strat.timeframe or "1M",
                            "expiry_minutes": strat.expiry_minutes,
                            "remaining_seconds": remaining_seconds,
                            "payout": payout,
                            "price": current_price,
                            "ev_edge": ev_res.get("edge_pct", 0.0),
                            "recommended_stake": rec_pos.get("stake", 10.0),
                            "martingale_step": rec_pos.get("step", 1)
                        }
                        logger.info(f"⚡ [PRE-SIGNAL RADAR] {symbol} {direction} ({strat.name}) ~{remaining_seconds}s remaining | Rec Stake: ${rec_pos['stake']} (Step {rec_pos['step']})")
                        self.safe_emit_js(f"if(window.onPreSignal) window.onPreSignal({json.dumps(pre_data)});")
                        await self.telegram.broadcast_pre_signal(
                            symbol=symbol,
                            direction=direction,
                            timeframe=strat.timeframe or "1M",
                            expiry_minutes=strat.expiry_minutes,
                            remaining_seconds=remaining_seconds,
                            price=current_price,
                            payout=payout,
                            strategy_name=strat.name
                        )
                        return
        except Exception as e:
            logger.debug(f"[PRE-SIGNAL] Evaluation note: {e}")

    def _on_candle_completed(self, symbol: str, candle: Candle):
        """Called upon 1-minute candle close. Triggers active user strategy evaluation."""
        if not self.running:
            return

        # Emit sealed completed candle to Live Interactive Chart
        try:
            candle_payload = json.dumps({
                "symbol": symbol,
                "candle": {
                    "timestamp": int(candle.timestamp),
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume)
                }
            })
            self.safe_emit_js(f"if(window.onCandleCompleted) window.onCandleCompleted({candle_payload});")
        except Exception:
            pass

        # Strategy evaluation and signal generation halted if scanner/tool is paused
        if self.scanning_paused or symbol in self.unwatched_symbols:
            return

        if self._loop:
            asyncio.run_coroutine_threadsafe(self._evaluate_strategies_for_asset(symbol, candle), self._loop)

    def _on_status_update(self, mode: str, text: str):
        logger.info(f"[BROKER STATUS] {mode.upper()}: {text}")
        latency = self.ws_client.latency_ms
        self.safe_emit_js(f"window.onBrokerStatus({json.dumps(mode)}, {json.dumps(text)}, {latency});")

    def _on_external_webhook(self, payload: dict):
        """Processes signals piped via external HTTP webhook (TradingView / MT4)."""
        symbol = payload.get("symbol")
        side = str(payload.get("side", "")).upper()
        duration = int(payload.get("duration", 2))

        if not symbol or side not in ("CALL", "PUT", "BUY", "SELL"):
            logger.warning(f"[WEBHOOK] Invalid alert payload: {payload}")
            return

        can_fire, lock_reason = self.tracker.can_dispatch_signal()
        if not can_fire:
            logger.info(f"[SEQUENTIAL LOCK] Webhook {symbol} skipped: {lock_reason}")
            return

        direction = "CALL" if side in ("CALL", "BUY") else "PUT"
        current_price = asset_registry.get_latest_price(symbol) or 1.0
        payout = asset_registry.get_payout(symbol) or 85.0

        sig = Signal(
            asset_symbol=symbol,
            direction=direction,
            duration_minutes=duration,
            entry_price=current_price,
            live_payout=payout,
            strategy_name=payload.get("strategy_name", "TradingView Alert Relay"),
            confidence=95
        )

        if not self.tracker.register_signal(sig):
            return

        sig_json = json.dumps(sig.to_dict())
        self.safe_emit_js(f"window.onSignalFired({sig_json});")

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.telegram.broadcast_signal(sig), self._loop)

    # -------------------------------------------------------------------------
    # Strategy Evaluation & Confluence Pipeline
    # -------------------------------------------------------------------------

    async def _evaluate_strategies_for_asset(self, symbol: str, trigger_candle: Candle):
        """Evaluates all active user-defined strategies against the completed candle."""
        # 0. Sequential Live Trade Lock & Dynamic Post-Loss Cooldown
        can_fire, lock_reason = self.tracker.can_dispatch_signal()
        if not can_fire:
            logger.debug(f"[SEQUENTIAL LOCK] {symbol} skipped: {lock_reason}")
            return

        # 1. Trading Session / Operating Hours Filter
        session_ok, session_msg = self.scheduler.is_session_active()
        if not session_ok:
            logger.debug(f"[SESSION SCHEDULER] Skipping {symbol}: {session_msg}")
            return

        # 2. Economic News Blackout Filter
        in_news_blackout, news_msg = self.news_calendar.is_in_blackout(symbol)
        if in_news_blackout:
            logger.info(f"[NEWS BLACKOUT] Skipping {symbol}: {news_msg}")
            return

        # 3. Daily Risk Management Circuit Breakers (Take Profit / Stop Loss)
        cb_halted, cb_msg = self.risk_manager.check_circuit_breaker()
        if cb_halted:
            if not self.scanning_paused:
                self.scanning_paused = True
                logger.warning(f"🛑 [CIRCUIT BREAKER] {cb_msg}. Halting scanner.")
                self.safe_emit_js(f"if(window.onCircuitBreakerTriggered) window.onCircuitBreakerTriggered({json.dumps(self.risk_manager.get_session_metrics())});")
            return

        candles_1m = self.candle_store.get_candles(symbol, "1M", contiguous_only=True)
        if len(candles_1m) < 15:
            # Fall back to raw buffer or database candles to ensure technical indicator calculation
            candles_1m = self.candle_store.get_candles(symbol, "1M", contiguous_only=False)
            if len(candles_1m) < 15:
                try:
                    from core.storage.db import db
                    db_candles = db.get_recent_candles(symbol, 50)
                    if len(db_candles) >= 15:
                        candles_1m = db_candles
                    else:
                        return  # Need minimal history depth
                except Exception:
                    return

        candles_3m = self.candle_store.get_candles(symbol, "3M")
        candles_5m = self.candle_store.get_candles(symbol, "5M")
        candles_15m = self.candle_store.get_candles(symbol, "15M")
        if not candles_5m and len(candles_1m) >= 5:
            candles_5m = self.candle_store._synthesize_timeframe(candles_1m, 300)
        if not candles_15m and len(candles_1m) >= 15:
            candles_15m = self.candle_store._synthesize_timeframe(candles_1m, 900)
        mtf_dict = {
            "1M": candles_1m,
            "3M": candles_3m,
            "5M": candles_5m,
            "15M": candles_15m
        }
        payout = asset_registry.get_payout(symbol)

        # Single-pass technical indicator snapshots
        snapshot_1m = TechnicalIndicatorEngine.calculate_technical_snapshot(candles_1m)
        is_5m_close = ((trigger_candle.timestamp + 60) % 300 == 0)
        snapshot_5m = None
        if is_5m_close and candles_5m and len(candles_5m) >= 5:
            snapshot_5m = TechnicalIndicatorEngine.calculate_technical_snapshot(candles_5m)

        # Flatline / Market Stagnation Guard
        is_otc = "(OTC)" in symbol or "_otc" in symbol.lower()
        if getattr(settings, "OTC_FLATLINE_GUARD", True) and is_otc:
            if snapshot_1m and snapshot_1m.get("is_flatlined"):
                logger.info(f"[FLATLINE GUARD] Stagnant OTC consolidation detected on {symbol}. Skipping evaluation.")
                return

        active_strategies = strategy_manager.get_active_strategies()
        triggered_setups = []

        for strat in active_strategies:
            try:
                # 1. Payout threshold filter
                if payout is None or payout < strat.min_payout:
                    continue

                # 2. Asset scope filter (assign particular strategies to particular currencies)
                scope = strat.assets or ["ALL_MARKETS"]
                in_scope = False
                if "ALL_MARKETS" in scope or "ALL" in scope:
                    in_scope = True
                elif "ALL_OTC" in scope and is_otc:
                    in_scope = True
                elif "ALL_REAL" in scope and not is_otc:
                    in_scope = True
                elif symbol in scope:
                    in_scope = True
                else:
                    # Check case-insensitive or normalized match (e.g. EUR/USD matching EUR/USD (OTC))
                    sym_clean = symbol.replace(" (OTC)", "").replace("_otc", "").replace("/", "").strip().upper()
                    for item in scope:
                        item_clean = item.replace(" (OTC)", "").replace("_otc", "").replace("/", "").strip().upper()
                        if sym_clean == item_clean:
                            in_scope = True
                            break
                if not in_scope:
                    continue

                # 3. Timeframe boundary & candle selection
                strat_tf = (strat.timeframe or "1M").upper()
                if strat_tf == "5M":
                    if not is_5m_close or not candles_5m or len(candles_5m) < 5:
                        continue
                    eval_candles = candles_5m
                    eval_trigger = candles_5m[-1]
                    eval_snapshot = snapshot_5m
                else:
                    eval_candles = candles_1m
                    eval_trigger = trigger_candle
                    eval_snapshot = snapshot_1m

                # 4. Anti-spam cooldown filter
                if not cooldown_manager.is_allowed(strat.id, symbol, eval_trigger.timestamp, strat.cooldown_seconds):
                    continue

                # 5. Compile and evaluate AST rule tree
                compiled_ast = StrategyCompiler.compile_strategy_ast(strat)
                directions = ["CALL", "PUT"] if strat.direction == "BOTH" else [strat.direction]

                for direction in directions:
                    passed, reason, details = PatternRuleEngine.evaluate_node(
                        compiled_ast,
                        eval_candles,
                        multi_timeframe_candles=mtf_dict,
                        technical_snapshot=eval_snapshot,
                        direction_context=direction
                    )

                    if passed:
                        # Engage cooldown immediately
                        cooldown_manager.record_signal(strat.id, symbol, eval_trigger.timestamp)

                        # Calculate quantitative Setup Quality Score
                        score, tier, audit = ConfluenceEngine.calculate_setup_quality_score(eval_trigger, payout, details, technical_snapshot=eval_snapshot, direction=direction)

                        # Evaluate Quant Expected Value (EV) positive-edge filter
                        ev_res = self.quant_ev.evaluate_edge(
                            symbol=symbol,
                            live_payout=payout or 85.0,
                            confidence_score=score
                        )
                        if not ev_res["passed"]:
                            logger.info(f"[QUANT EV GATED] {symbol} ({strat.name}): {ev_res['reason']}")
                            continue

                        # Risk Management Position Sizing & Martingale Recommendation
                        rec_pos = self.risk_manager.get_recommended_stake()
                        audit["quant_ev"] = ev_res
                        audit["recommended_stake"] = rec_pos["stake"]
                        audit["martingale_step"] = rec_pos["step"]
                        audit["is_martingale"] = rec_pos["is_martingale"]

                        # Create confirmed Signal
                        sig = Signal(
                            strategy_id=strat.id,
                            strategy_name=strat.name,
                            asset_symbol=symbol,
                            direction=direction,
                            timeframe=strat.timeframe,
                            duration_minutes=strat.expiry_minutes,
                            entry_price=eval_trigger.close,
                            live_payout=payout,
                            confidence=score,
                            audit_trail=audit
                        )
                        triggered_setups.append({
                            "strat": strat,
                            "sig": sig,
                            "candles": eval_candles,
                            "score": score,
                            "tier": tier,
                            "direction": direction
                        })
                        break
            except Exception as strat_err:
                logger.warning(
                    f"[STRATEGY EVAL ERROR] Strategy '{strat.name}' ({strat.id}) failed on {symbol}: {strat_err}",
                    exc_info=True
                )
                continue

        if not triggered_setups:
            return

        # Multi-Strategy Confluence Scanner ("Super Signals")
        same_direction_setups = {}
        for s in triggered_setups:
            d = s["direction"]
            if d not in same_direction_setups:
                same_direction_setups[d] = []
            same_direction_setups[d].append(s)

        for d, setups in same_direction_setups.items():
            if len(setups) >= 2 and getattr(settings, "CONFLUENCE_SCANNER_ENABLED", True):
                strat_names = [s["strat"].name for s in setups]
                primary = setups[0]
                sig = primary["sig"]
                sig.strategy_name = f"⭐ ULTRA CONFLUENCE ({len(setups)} Strats: {', '.join(strat_names)})"
                sig.confidence = min(99.0, max(s["score"] for s in setups) + 8.0)
                sig.audit_trail["confluence_strategies"] = strat_names
                tier = "SSS (Ultra Confluence)"

                logger.info(
                    f"⭐ [ULTRA CONFLUENCE TRIGGERED] {len(setups)} strategies ({', '.join(strat_names)}) on {symbol} "
                    f"({d} @ {sig.entry_price}) — Confluence Score: {sig.confidence}%"
                )

                self.tracker.register_signal(sig)
                chart_bytes = await ChartGenerator.render_chart_async(primary["candles"], sig)
                sig_json = json.dumps(sig.to_dict())
                self.safe_emit_js(f"window.onSignalFired({sig_json});")
                await self.telegram.broadcast_signal(sig, chart_bytes)
            else:
                for s in setups:
                    if self.tracker.sequential_trade_lock and self.tracker.is_trade_active():
                        logger.debug(f"[SEQUENTIAL LOCK] Skipping subsequent setup {s['sig'].strategy_name} on {symbol} because an active trade is in progress.")
                        break
                    sig = s["sig"]
                    logger.info(
                        f"🚀 [SIGNAL TRIGGERED] {sig.strategy_name} on {symbol} "
                        f"({s['direction']} @ {sig.entry_price}) — Setup Quality: {s['score']}% ({s['tier']})"
                    )
                    if not self.tracker.register_signal(sig):
                        continue
                    chart_bytes = await ChartGenerator.render_chart_async(s["candles"], sig)
                    sig_json = json.dumps(sig.to_dict())
                    self.safe_emit_js(f"window.onSignalFired({sig_json});")
                    await self.telegram.broadcast_signal(sig, chart_bytes)

    # -------------------------------------------------------------------------
    # Trade Outcome Lifecycle Handler
    # -------------------------------------------------------------------------

    def _on_trade_outcome(self, signal: Signal):
        """Dispatches post-expiry WIN/LOSS alerts to Telegram and updates dashboard."""
        # Update Risk Manager telemetry and check TP/SL limits
        self.risk_manager.record_trade_outcome(
            outcome=signal.status,
            payout_pct=signal.live_payout or 85.0,
            stake=getattr(signal, "recommended_stake", None)
        )
        cb_active, cb_reason = self.risk_manager.check_circuit_breaker()
        if cb_active and not self.scanning_paused:
            self.scanning_paused = True
            logger.warning(f"🛑 [CIRCUIT BREAKER] {cb_reason}. Auto-pausing scanner.")
            self.safe_emit_js(f"if(window.onCircuitBreakerTriggered) window.onCircuitBreakerTriggered({json.dumps(self.risk_manager.get_session_metrics())});")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.telegram.broadcast_circuit_breaker(self.risk_manager.get_session_metrics()),
                    self._loop
                )

        if self._loop:
            asyncio.run_coroutine_threadsafe(self.telegram.broadcast_outcome(signal), self._loop)

        sig_json = json.dumps(signal.to_dict())
        self.safe_emit_js(f"window.onTradeOutcome({sig_json});")

    # -------------------------------------------------------------------------
    # Telegram Remote Commands Router
    # -------------------------------------------------------------------------

    def _on_telegram_command(self, chat_id: str, cmd_text: str, context: dict):
        """Processes interactive incoming commands from Telegram."""
        if not self._loop:
            return

        cmd = cmd_text.lower().strip()

        # Public commands: available to all users
        if cmd in ["/start", "/help"]:
            reply = (
                f"⚡ <b>TradePulse Quotex Signal Bot</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Welcome, {context.get('user_name', 'Trader')}!\n\n"
                f"Public Commands:\n"
                f"• <b>/subscribe</b> — Opt-in to real-time VIP trade signals\n"
                f"• <b>/unsubscribe</b> — Opt-out of signal notifications\n\n"
                f"Administrator Commands (Restricted):\n"
                f"• <b>/stats</b> — Win rate, wins, losses & strategy rankings\n"
                f"• <b>/bestpairs</b> — Top winning currency pairs today\n"
                f"• <b>/status</b> — Live scanning telemetry\n"
                f"• <b>/markets</b> — Current 30+ OTC rates & payouts\n"
                f"• <b>/strats</b> — Active strategy list\n"
                f"• <b>/pause</b> — Pause market scanner\n"
                f"• <b>/resume</b> — Resume market scanner\n\n"
                f"🔒 <i>Safe Mode: 100% Real-Time Market Confluence</i>"
            )
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, reply), self._loop)
            return

        # Fail-closed Administrative authorization check (P1-1)
        is_admin = self.telegram.is_admin(chat_id)
        privileged_cmds = [
            "/status", "cmd_status", "/markets", "cmd_markets",
            "/strategies", "/strategy", "/strats", "/stats", "/bestpairs", "/pause", "/resume"
        ]

        if cmd in privileged_cmds:
            if not is_admin:
                logger.warning(f"[TELEGRAM AUTH] Refused privileged command '{cmd}' from unauthorized chat {chat_id}.")
                denied_msg = (
                    "⛔ <b>Access Denied</b>: This command requires administrator privileges.\n"
                    "<i>Your chat ID is not listed in TELEGRAM_ADMIN_CHAT_IDS.</i>"
                )
                asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, denied_msg), self._loop)
                return

        if cmd in ["/status", "cmd_status"]:
            stats = db.get_performance_stats()
            active_strats = len(strategy_manager.get_active_strategies())
            rep = TelegramFormatter.format_status_report(
                uptime_seconds=time.time() - self.start_time,
                latency_ms=self.ws_client.latency_ms,
                connected_pairs=len(self.candle_store.get_symbols()),
                active_strategies=active_strats,
                total_signals=stats.get("total_signals", 0),
                win_rate=stats.get("win_rate", 0.0)
            )
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, rep), self._loop)

        elif cmd in ["/stats"]:
            stats = db.get_performance_stats()
            tot = stats.get("total_signals", 0)
            wins = stats.get("wins", 0)
            losses = stats.get("losses", 0)
            draws = stats.get("draws", 0)
            wr = stats.get("win_rate", 0.0)

            strat_lines = []
            for s in stats.get("strategy_breakdown", [])[:5]:
                strat_lines.append(f"• <b>{s['strategy_name']}</b>: {s['win_rate']}% ({s['wins']}W / {s['losses']}L)")
            strat_txt = "\n".join(strat_lines) if strat_lines else "<i>No completed trades today yet</i>"

            reply = (
                f"📊 <b>TRADEPULSE PERFORMANCE STATS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Total Signals:</b> <b>{tot}</b>\n"
                f"✅ <b>Wins:</b> <b>{wins}</b>\n"
                f"❌ <b>Losses:</b> <b>{losses}</b>\n"
                f"⏸ <b>Draws:</b> <b>{draws}</b>\n"
                f"🏆 <b>Session Win Rate:</b> <b>{wr:.1f}%</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>Top Strategies:</b>\n"
                f"{strat_txt}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 <i>Safe Mode: 100% Real-Time Market Confluence</i>"
            )
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, reply), self._loop)

        elif cmd in ["/bestpairs"]:
            stats = db.get_performance_stats()
            top_pairs = stats.get("top_pairs", [])
            pair_lines = []
            for p in top_pairs[:7]:
                payout = asset_registry.get_payout(p["symbol"])
                payout_str = f" ({payout:.0f}%)" if payout else ""
                pair_lines.append(f"• <code>{p['symbol']}</code>{payout_str}: <b>{p['win_rate']}%</b> ({p['wins']}W / {p['losses']}L)")
            pairs_txt = "\n".join(pair_lines) if pair_lines else "<i>Calibrating pair performance...</i>"

            reply = (
                f"🏆 <b>TOP PERFORMING CURRENCY PAIRS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{pairs_txt}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Sorted by win rate and trading volume today.</i>"
            )
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, reply), self._loop)

        elif cmd in ["/markets", "cmd_markets"]:
            syms = asset_registry.get_all_symbols()
            rep = TelegramFormatter.format_markets_table(syms[:20])
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, rep), self._loop)

        elif cmd in ["/strategies", "/strategy", "/strats"]:
            strats = strategy_manager.get_all_strategies()
            lines = ["🎯 <b>YOUR CUSTOM STRATEGIES</b>\n━━━━━━━━━━━━━━━━━━━━"]
            for s in strats:
                status_icon = "🟢 ACTIVE" if s.enabled else "⚪ PAUSED"
                lines.append(f"• <b>{s.name}</b>: {status_icon} ({s.direction} / {s.expiry_minutes}m)")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, "\n".join(lines)), self._loop)

        elif cmd == "/pause":
            self.scanning_paused = True
            logger.info(f"[ENGINE] Scanning paused remotely by admin {chat_id}.")
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, "⏸ <b>Market scanner PAUSED remotely.</b>"), self._loop)

        elif cmd == "/resume":
            self.scanning_paused = False
            logger.info(f"[ENGINE] Scanning resumed remotely by admin {chat_id}.")
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, "▶️ <b>Market scanner RESUMED remotely.</b>"), self._loop)


# -----------------------------------------------------------------------------
# PyWebView Bridge API Class
# -----------------------------------------------------------------------------

class TradePulseBridgeAPI:
    """Exposes Python backend methods directly to desktop JavaScript frontend."""

    def __init__(self, engine: TradePulseEngine):
        self.engine = engine
        self.current_broker_base = "https://qxbroker.com"
        self._main_win = None
        self._main_form = None
        self._broker_panel = None
        self._broker_wv = None
        self._Action = None
        self._Drawing = None
        self._ipc_queue: queue.Queue = queue.Queue(maxsize=5000)
        self._ipc_worker_started = False
        self._auto_primer_started = False
        self._broker_is_on_screen = False
        self._broker_last_rect = None

        def _on_dyn_asset(item):
            try:
                all_assets = asset_registry.get_all_asset_defs()
                self.engine.safe_emit_js(f"if (window.onAssetsUpdated) window.onAssetsUpdated({json.dumps(all_assets)});")
            except Exception:
                pass
        asset_registry.add_asset_added_callback(_on_dyn_asset)

    def _run_on_ui(self, func):
        """Executes a function on the WinForms UI thread safely without synchronous deadlocks."""
        if not self._main_form:
            return
        Action = self._Action or __import__('System', fromlist=['Action']).Action
        try:
            if hasattr(self._main_form, 'InvokeRequired') and self._main_form.InvokeRequired:
                self._main_form.BeginInvoke(Action(func))
            else:
                func()
        except Exception as e:
            logger.debug(f"[UI THREAD] _run_on_ui note: {e}")

    def init_embedded_broker(self):
        """Initializes native Microsoft Edge WebView2 control embedded directly inside an anchored container panel."""
        try:
            import clr
            from webview.util import interop_dll_path
            clr.AddReference('System.Windows.Forms')
            clr.AddReference('System.Drawing')
            clr.AddReference(interop_dll_path('Microsoft.Web.WebView2.Core.dll'))
            clr.AddReference(interop_dll_path('Microsoft.Web.WebView2.WinForms.dll'))

            WinForms = __import__('System.Windows.Forms', fromlist=['*'])
            Drawing = __import__('System.Drawing', fromlist=['*'])
            wv_winforms = __import__('Microsoft.Web.WebView2.WinForms', fromlist=['WebView2', 'CoreWebView2CreationProperties'])
            WebView2 = wv_winforms.WebView2
            CoreWebView2CreationProperties = wv_winforms.CoreWebView2CreationProperties
            Action = __import__('System', fromlist=['Action']).Action
            self._Action = Action
            self._Drawing = Drawing
            from webview.platforms.winforms import BrowserView

            if self._broker_wv:
                return True

            if not self._main_win:
                return False

            if not self._main_form:
                self._main_form = BrowserView.instances.get(self._main_win.uid)

            if not self._main_form:
                for _ in range(30):
                    time.sleep(0.1)
                    if self._main_win:
                        self._main_form = BrowserView.instances.get(self._main_win.uid)
                    if self._main_form:
                        break

            if not self._main_form:
                logger.warning("[BROKER TERMINAL] _main_form not yet available. Deferring init.")
                return False

            if hasattr(self._main_form, 'IsHandleCreated') and not self._main_form.IsHandleCreated:
                for _ in range(30):
                    time.sleep(0.1)
                    if self._main_form.IsHandleCreated:
                        break

            if hasattr(self._main_form, 'IsHandleCreated') and not self._main_form.IsHandleCreated:
                logger.warning("[BROKER TERMINAL] Form handle not yet created. Deferring init.")
                return False

            logger.info("[BROKER TERMINAL] Initializing embedded broker panel and native WebView2...")

            def create_wv():
                try:
                    # Hook form closing to properly dispose native controls
                    def on_form_closing(s, e):
                        try:
                            if self._broker_wv:
                                self._broker_wv.Dispose()
                                self._broker_wv = None
                            if self._broker_panel:
                                self._broker_panel.Dispose()
                                self._broker_panel = None
                        except Exception:
                            pass
                    self._main_form.FormClosing += on_form_closing

                    # Hook form resize to dynamically adjust embedded panel
                    def on_form_resize(s, e):
                        try:
                            if self._broker_panel:
                                is_min = hasattr(self._main_form, 'WindowState') and str(self._main_form.WindowState) == 'Minimized'
                                if is_min or not getattr(self, '_broker_is_on_screen', False):
                                    self._broker_panel.Visible = False
                                    self._broker_panel.SendToBack()
                                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
                                    return

                                scale = float(getattr(self._main_form, '_scale', 1.0))
                                if getattr(self, '_broker_last_rect', None):
                                    rx, ry, rw, rh = self._broker_last_rect
                                    self._broker_panel.Location = Drawing.Point(int(rx * scale), int(ry * scale))
                                    self._broker_panel.Size = Drawing.Size(int(rw * scale), int(rh * scale))
                                else:
                                    init_x = int(240 * scale)
                                    init_y = int(52 * scale)
                                    init_w = max(200, self._main_form.ClientSize.Width - init_x)
                                    init_h = max(200, self._main_form.ClientSize.Height - init_y)
                                    self._broker_panel.Location = Drawing.Point(init_x, init_y)
                                    self._broker_panel.Size = Drawing.Size(init_w, init_h)
                        except Exception:
                            pass
                    self._main_form.Resize += on_form_resize

                    scale = float(getattr(self._main_form, '_scale', 1.0))

                    # Create dedicated native panel with manual coordinate management (Anchor=None prevents OS auto-warping)
                    self._broker_panel = WinForms.Panel()
                    self._broker_panel.BackColor = Drawing.Color.FromArgb(11, 14, 20)

                    init_x = int(240 * scale)
                    init_y = int(52 * scale)
                    init_w = max(200, self._main_form.ClientSize.Width - init_x)
                    init_h = max(200, self._main_form.ClientSize.Height - init_y)

                    # Start hidden and safely parked off-screen
                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
                    self._broker_panel.Size = Drawing.Size(init_w, init_h)
                    self._broker_panel.Anchor = getattr(WinForms.AnchorStyles, 'None')
                    self._broker_panel.Visible = False

                    self._broker_wv = WebView2()
                    props = CoreWebView2CreationProperties()
                    props.UserDataFolder = str(settings.resolved_data_dir / "broker_session")
                    # Chromium flags to prevent Edge WebView2 from throttling or suspending background timers and WebSockets
                    props.AdditionalBrowserArguments = (
                        "--disable-background-timer-throttling "
                        "--disable-backgrounding-occluded-windows "
                        "--disable-renderer-backgrounding"
                    )
                    self._broker_wv.CreationProperties = props
                    self._broker_wv.Dock = WinForms.DockStyle.Fill

                    self._broker_panel.Controls.Add(self._broker_wv)
                    self._main_form.Controls.Add(self._broker_panel)

                    def on_ready(s, e):
                        if not e.IsSuccess:
                            err_msg = str(e.InitializationException)
                            logger.error(f"[BROKER TERMINAL] Embedded WebView2 failed to initialize: {err_msg}")
                            # Fallback: if user data folder is locked (0x800700AA), try an isolated PID-specific directory
                            if not getattr(self, '_fallback_attempted', False):
                                self._fallback_attempted = True
                                try:
                                    fallback_dir = settings.resolved_data_dir / f"broker_session_{os.getpid()}"
                                    logger.info(f"[BROKER TERMINAL] Attempting recovery with isolated profile: {fallback_dir}")
                                    fallback_props = CoreWebView2CreationProperties()
                                    fallback_props.UserDataFolder = str(fallback_dir)
                                    fallback_props.AdditionalBrowserArguments = (
                                        "--disable-background-timer-throttling "
                                        "--disable-backgrounding-occluded-windows "
                                        "--disable-renderer-backgrounding"
                                    )
                                    self._broker_panel.Controls.Clear()
                                    self._broker_wv = WebView2()
                                    self._broker_wv.CreationProperties = fallback_props
                                    self._broker_wv.Dock = WinForms.DockStyle.Fill
                                    self._broker_panel.Controls.Add(self._broker_wv)
                                    self._on_ready_handler = on_ready
                                    self._broker_wv.CoreWebView2InitializationCompleted += self._on_ready_handler
                                    self._broker_wv.EnsureCoreWebView2Async(None)
                                except Exception as fe:
                                    logger.error(f"[BROKER TERMINAL] Fallback initialization error: {fe}")
                            return

                        logger.info("[BROKER TERMINAL] Embedded native WebView2 initialized! Registering pre-execution hooks...")

                        # User-Agent spoofing to bypass Cloudflare bot detection
                        try:
                            self._broker_wv.CoreWebView2.Settings.UserAgent = (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                            )
                        except Exception as ue:
                            logger.debug(f"[BROKER TERMINAL] UserAgent setting note: {ue}")

                        # Register script to execute on document created for ALL pages and reloads
                        from core.ingester.auth_manager import STREAM_INJECTION_JS
                        try:
                            self._broker_wv.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(STREAM_INJECTION_JS)
                            logger.info("[BROKER TERMINAL] Pre-execution stream interceptor registered on document creation pipeline.")
                        except Exception as se:
                            logger.debug(f"[BROKER TERMINAL] AddScriptToExecuteOnDocumentCreatedAsync error: {se}")

                        # Assign to auth_manager with thread-safe UI marshalled evaluate_js
                        class EmbeddedWindowAdapter:
                            def __init__(self, api, wv):
                                self._api = api
                                self._wv = wv
                            def evaluate_js(self, js):
                                def do_exec():
                                    try:
                                        if self._wv and hasattr(self._wv, 'CoreWebView2') and self._wv.CoreWebView2:
                                            self._wv.CoreWebView2.ExecuteScriptAsync(js)
                                    except Exception:
                                        pass
                                self._api._run_on_ui(do_exec)

                        auth_manager.broker_window = EmbeddedWindowAdapter(self, self._broker_wv)

                        # Dedicated single background worker for IPC message processing
                        def ipc_worker():
                            import time as _pytime
                            import json as _pyjson
                            while True:
                                try:
                                    msg_str = self._ipc_queue.get()
                                    if not msg_str:
                                        continue
                                    now = _pytime.time()
                                    self.engine.ws_client._last_heartbeat = now
                                    data = _pyjson.loads(msg_str)
                                    msg_type = data.get("type")
                                    if msg_type == "frame":
                                        self.on_broker_frame(data.get("data", ""))
                                    elif msg_type == "payouts":
                                        self.on_broker_payouts(data.get("data", {}))
                                    elif msg_type == "instruments":
                                        self.on_broker_instruments(data.get("data", []))
                                    elif msg_type == "tick":
                                        self.on_broker_tick(
                                            data.get("symbol", ""),
                                            float(data.get("price", 0)),
                                            data.get("source", "unknown")
                                        )
                                    elif msg_type == "candles":
                                        self.on_broker_candles(
                                            data.get("asset") or data.get("symbol") or "",
                                            data.get("data", [])
                                        )
                                    elif msg_type == "session":
                                        token = data.get("token")
                                        if token and len(token) > 10 and token != self.engine.session_token:
                                            logger.info("[BROKER TERMINAL] Intercepted genuine active user session token from Quotex!")
                                            auth_manager.store_session(token)
                                            self.engine.session_token = token
                                            self.engine.ws_client.session_token = token
                                            self.engine.restart_ingestion()
                                    elif msg_type == "telemetry":
                                        logger.info(f"[BROKER JS] {data.get('text', '')}")
                                except Exception as ex:
                                    logger.warning(f"[IPC] Worker note: {ex}")

                        if not self._ipc_worker_started:
                            self._ipc_worker_started = True
                            threading.Thread(target=ipc_worker, daemon=True, name="TradePulse-IPC-Worker").start()

                        # Hook WebMessageReceived for native two-way IPC (non-blocking queue dispatch)
                        def on_msg(sender, args):
                            try:
                                raw = None
                                try:
                                    raw = args.WebMessageAsJson
                                except Exception as we:
                                    logger.warning(f"[IPC] WebMessageAsJson error: {we}")
                                if not raw:
                                    try:
                                        raw = args.TryGetWebMessageAsString()
                                    except Exception:
                                        pass
                                if raw and self._ipc_queue:
                                    try:
                                        self._ipc_queue.put_nowait(raw)
                                    except queue.Full:
                                        pass
                            except Exception as ex:
                                logger.warning(f"[IPC] on_msg exception: {ex}")

                        self._on_web_msg_handler = on_msg
                        self._broker_wv.CoreWebView2.WebMessageReceived += self._on_web_msg_handler

                        # Hook ProcessFailed to automatically recover WebView2 if renderer ever encounters an issue
                        def on_proc_failed(s, e):
                            try:
                                logger.warning(f"[BROKER TERMINAL] WebView2 process event: {getattr(e, 'ProcessFailedKind', 'unknown')}")
                                def do_reload():
                                    try:
                                        if self._broker_wv:
                                            self._broker_wv.Reload()
                                    except Exception:
                                        pass
                                self._run_on_ui(do_reload)
                            except Exception:
                                pass

                        try:
                            self._on_proc_failed_handler = on_proc_failed
                            self._broker_wv.CoreWebView2.ProcessFailed += self._on_proc_failed_handler
                        except Exception:
                            pass

                        # Helper to extract authentic cookies from CookieManager safely on UI thread
                        def check_and_extract_session(target_url):
                            try:
                                Action = self._Action or __import__('System', fromlist=['Action']).Action
                                Task = __import__('System.Threading.Tasks', fromlist=['Task']).Task
                                task = self._broker_wv.CoreWebView2.CookieManager.GetCookiesAsync(target_url)

                                def on_cookies_done(t):
                                    def parse_cookies():
                                        try:
                                            cookie_list = t.Result
                                            cookies_dict = {}
                                            extracted_token = None
                                            for i in range(cookie_list.Count):
                                                c = cookie_list.Item[i]
                                                cookies_dict[c.Name] = c.Value
                                                if c.Name.lower() in ("token", "ssid"):
                                                    extracted_token = c.Value

                                            if extracted_token and len(extracted_token) > 10 and len(cookies_dict) >= 2:
                                                if self.engine.session_token != extracted_token:
                                                    logger.info(f"[BROKER TERMINAL] Extracted authentic live session token & {len(cookies_dict)} cookies from Quotex!")
                                                    auth_manager.store_session(extracted_token, cookies=cookies_dict)
                                                    self.engine.session_token = extracted_token
                                                    self.engine.ws_client.session_token = extracted_token
                                                    self.engine.restart_ingestion()
                                        except Exception as ce:
                                            logger.debug(f"[BROKER TERMINAL] Cookie read note: {ce}")

                                    self._run_on_ui(parse_cookies)

                                task.ContinueWith(Action[Task](on_cookies_done))
                            except Exception as te:
                                logger.debug(f"[BROKER TERMINAL] Cookie task note: {te}")

                        # Hook NavigationCompleted to auto-inject stream interceptor & verify session
                        def on_nav_completed(sender, args):
                            try:
                                url = sender.Source or ""
                                is_success = getattr(args, 'IsSuccess', True)
                                error_status = str(getattr(args, 'WebErrorStatus', ''))
                                logger.info(f"[BROKER TERMINAL] Navigated to: {url} (success={is_success}, status={error_status})")

                                # Only fallback to alternate mirror on genuine network failures, not normal redirects or cancellations
                                if not is_success:
                                    is_cancel = any(k in error_status.lower() for k in ["cancel", "abort"])
                                    if not is_cancel:
                                        logger.warning(f"[BROKER TERMINAL] Navigation failure for {url} ({error_status}). Attempting fallback mirror...")
                                        for mirror in ["https://qx-market.com", "https://qxbroker.io", "https://quotex-broker.com"]:
                                            if mirror not in url:
                                                self.current_broker_base = mirror
                                                sender.Navigate(f"{mirror}/en/sign-in")
                                                return

                                from core.ingester.auth_manager import STREAM_INJECTION_JS
                                sender.ExecuteScriptAsync(STREAM_INJECTION_JS)

                                if any(k in url.lower() for k in ["/trade", "demo-trade", "qxbroker", "quotex"]):
                                    check_and_extract_session(url)
                                    sender.ExecuteScriptAsync("if(window.__tp_scan_now) window.__tp_scan_now();")
                                    sender.ExecuteScriptAsync("if(window.__tp_subscribe_all) window.__tp_subscribe_all();")
                            except Exception as ne:
                                logger.debug(f"[BROKER TERMINAL] Nav hook note: {ne}")

                        self._on_nav_handler = on_nav_completed
                        self._broker_wv.CoreWebView2.NavigationCompleted += self._on_nav_handler

                        # Background poller to maintain continuous stream injection & session extraction
                        def poll_session_status():
                            import time as _pytime
                            last_sub_time = 0.0
                            while self._broker_wv and self._main_form:
                                _pytime.sleep(5.0)
                                try:
                                    now = _pytime.time()
                                    should_resub = (now - last_sub_time) > 60.0
                                    def check_ui():
                                        nonlocal last_sub_time
                                        try:
                                            if self._broker_wv and hasattr(self._broker_wv, 'CoreWebView2') and self._broker_wv.CoreWebView2:
                                                current_url = self._broker_wv.CoreWebView2.Source or ""
                                                if any(k in current_url.lower() for k in ["/trade", "demo-trade", "qxbroker", "quotex"]):
                                                    check_and_extract_session(current_url)
                                                    if should_resub:
                                                        last_sub_time = now
                                                        from core.ingester.auth_manager import STREAM_INJECTION_JS
                                                        self._broker_wv.CoreWebView2.ExecuteScriptAsync(STREAM_INJECTION_JS)
                                                        self._broker_wv.CoreWebView2.ExecuteScriptAsync("if(window.__tp_scan_now) window.__tp_scan_now();")
                                                        self._broker_wv.CoreWebView2.ExecuteScriptAsync("if(window.__tp_subscribe_all) window.__tp_subscribe_all();")
                                        except Exception as pe:
                                            logger.debug(f"[POLL SESSION] Note: {pe}")
                                    self._run_on_ui(check_ui)
                                except Exception:
                                    pass
                        threading.Thread(target=poll_session_status, daemon=True).start()

                        # Navigate to Quotex (sign-in or trade room)
                        target_url = f"{self.current_broker_base}/en/trade" if self.engine.session_token else f"{self.current_broker_base}/en/sign-in"
                        logger.info(f"[BROKER TERMINAL] Navigating to primary mirror: {target_url}")
                        self._broker_wv.CoreWebView2.Navigate(target_url)

                    self._broker_wv.CoreWebView2InitializationCompleted += on_ready
                    self._broker_wv.EnsureCoreWebView2Async(None)
                    self._start_auto_primer()
                except Exception as ex:
                    logger.error(f"[BROKER TERMINAL] Failed to create embedded WebView2: {ex}")

            self._run_on_ui(create_wv)
            return True
        except Exception as e:
            logger.error(f"[BROKER TERMINAL] init_embedded_broker error: {e}")
            return False

    def set_broker_visible(self, visible: bool):
        """Directly toggles visibility of the native embedded broker station."""
        self._broker_is_on_screen = bool(visible)
        if not visible:
            self._broker_last_rect = None

        if visible and (not self._broker_panel or not self._broker_wv):
            logger.info("[BROKER TERMINAL] Broker controls not ready on set_broker_visible. Initializing on demand...")
            self.init_embedded_broker()

        if not self._broker_panel or not self._main_form:
            return False

        Drawing = self._Drawing or __import__('System.Drawing', fromlist=['*'])

        def do_vis():
            try:
                scale = float(getattr(self._main_form, '_scale', 1.0))
                init_x = int(240 * scale)
                init_y = int(52 * scale)
                init_w = max(200, self._main_form.ClientSize.Width - init_x)
                init_h = max(200, self._main_form.ClientSize.Height - init_y)

                if visible:
                    self._broker_is_on_screen = True
                    self._broker_last_rect = (init_x / scale, init_y / scale, init_w / scale, init_h / scale)
                    self._broker_panel.Location = Drawing.Point(init_x, init_y)
                    self._broker_panel.Size = Drawing.Size(init_w, init_h)
                    self._broker_panel.Visible = True
                    if self._broker_wv:
                        self._broker_wv.Visible = True
                        self._broker_wv.BringToFront()
                    self._broker_panel.BringToFront()
                    # Trigger scan and subscription when user views Quotex terminal
                    try:
                        from core.ingester.auth_manager import STREAM_INJECTION_JS
                        if self._broker_wv and hasattr(self._broker_wv, 'CoreWebView2') and self._broker_wv.CoreWebView2:
                            self._broker_wv.CoreWebView2.ExecuteScriptAsync(STREAM_INJECTION_JS)
                            self._broker_wv.CoreWebView2.ExecuteScriptAsync("if(window.__tp_scan_now) window.__tp_scan_now();")
                            self._broker_wv.CoreWebView2.ExecuteScriptAsync("if(window.__tp_subscribe_all) window.__tp_subscribe_all();")
                    except Exception as ie:
                        logger.debug(f"[BROKER TERMINAL] Activation script note: {ie}")
                else:
                    self._broker_is_on_screen = False
                    self._broker_last_rect = None
                    self._broker_panel.Visible = False
                    self._broker_panel.SendToBack()
                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
                    self._broker_panel.Size = Drawing.Size(init_w, init_h)
            except Exception as e:
                logger.debug(f"[BROKER TERMINAL] set_broker_visible note: {e}")

        self._run_on_ui(do_vis)
        return True

    def sync_broker_position(self, x, y, w, h, visible):
        """Smoothly aligns the embedded native broker panel over the target container."""
        is_vis = bool(visible and w > 20 and h > 20)
        self._broker_is_on_screen = is_vis
        if is_vis:
            self._broker_last_rect = (x, y, w, h)
        else:
            self._broker_last_rect = None

        if visible and (not self._broker_panel or not self._broker_wv):
            self.init_embedded_broker()

        if not self._broker_panel or not self._main_form:
            return False

        Drawing = self._Drawing or __import__('System.Drawing', fromlist=['*'])

        def do_sync():
            try:
                scale = float(getattr(self._main_form, '_scale', 1.0))
                if is_vis:
                    self._broker_is_on_screen = True
                    self._broker_last_rect = (x, y, w, h)
                    self._broker_panel.Location = Drawing.Point(int(x * scale), int(y * scale))
                    self._broker_panel.Size = Drawing.Size(int(w * scale), int(h * scale))
                    self._broker_panel.Visible = True
                    if self._broker_wv:
                        self._broker_wv.Visible = True
                        self._broker_wv.BringToFront()
                    self._broker_panel.BringToFront()
                else:
                    self._broker_is_on_screen = False
                    self._broker_last_rect = None
                    self._broker_panel.Visible = False
                    self._broker_panel.SendToBack()
                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
            except Exception:
                pass

        self._run_on_ui(do_sync)
        return True

    def refresh_broker(self):
        """Reloads the embedded broker trading interface."""
        if not self._broker_wv:
            self.init_embedded_broker()
        if self._broker_wv and self._main_form:
            def do_reload():
                try:
                    self._broker_wv.Reload()
                except Exception:
                    pass
            self._run_on_ui(do_reload)
        return True

    def navigate_broker(self, url: str):
        """Directly navigates the embedded broker to any URL (supporting official domain mirrors)."""
        if not self._broker_wv:
            self.init_embedded_broker()
        if self._broker_wv and self._main_form:
            try:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme and parsed.netloc:
                    self.current_broker_base = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                pass
            def do_nav():
                try:
                    self._broker_wv.CoreWebView2.Navigate(url)
                except Exception:
                    pass
            self._run_on_ui(do_nav)
        return True

    def navigate_broker_signin(self):
        """Directly navigates the embedded broker to /en/sign-in page."""
        return self.navigate_broker(f"{self.current_broker_base}/en/sign-in")

    def navigate_broker_trade(self):
        """Directly navigates the embedded broker to /en/trade room."""
        return self.navigate_broker(f"{self.current_broker_base}/en/trade")

    def clear_broker_session(self):
        """Clears persisted user session credentials and resets engine connection state."""
        auth_manager.clear_session()
        self.engine.session_token = None
        self.engine.ws_client.session_token = None
        self.engine.ws_client._connected = False
        self.engine.ws_client._update_status("disconnected", "Session Cleared (Login Required)")
        return True

    def get_initial_state(self):
        self.engine.ui_ready = True
        return {
            "connected": self.engine.ws_client.is_connected,
            "latency": self.engine.ws_client.latency_ms,
            "status_text": "Connected" if self.engine.ws_client.is_connected else "Disconnected (Login Required)",
            "session_token": self.engine.session_token,
            "assets": asset_registry.get_all_asset_defs(),
            "payouts": asset_registry.get_live_payouts(),
            "prices": asset_registry.get_all_prices(),
            "price_sources": asset_registry.get_all_price_sources(),
            "strategies": [s.model_dump() for s in strategy_manager.get_all_strategies()],
            "stats": db.get_performance_stats(),
            "signals": [s for s in db.get_recent_signals(15)],
            "telegram_token": settings.TELEGRAM_BOT_TOKEN,
            "telegram_chat_id": settings.TELEGRAM_CHAT_IDS,
            "telegram_manager": self.engine.telegram_manager.get_config(),
            "webhook_endpoint": "http://127.0.0.1:8765/webhook",
            "global_cooldown": cooldown_manager.global_cooldown_seconds or 120,
            "engine_running": self.engine.running,
            "tool_active": not self.engine.scanning_paused,
            "scanning_paused": self.engine.scanning_paused,
            "advanced_filters": self.get_advanced_filters_config(),
            "risk_metrics": self.get_risk_session_metrics(),
            "upcoming_news": self.get_upcoming_news_events(6)
        }

    def get_all_assets(self):
        return asset_registry.get_all_asset_defs()

    def get_strategies(self):
        return [s.model_dump() for s in strategy_manager.get_all_strategies()]

    def save_strategy(self, data):
        return strategy_manager.save_or_update(data).model_dump()

    def toggle_strategy(self, strategy_id, enabled=None):
        return strategy_manager.toggle_strategy(strategy_id, enabled)

    def delete_strategy(self, strategy_id):
        return strategy_manager.delete_strategy(strategy_id)

    def set_tool_active(self, is_active: bool):
        """Starts or stops the live market signal scanner / strategy evaluation tool."""
        self.engine.scanning_paused = not bool(is_active)
        logger.info(f"[TOOL] Signal scanner {'STARTED (Active)' if is_active else 'STOPPED (Paused)'}")
        return {
            "success": True,
            "active": bool(is_active),
            "paused": self.engine.scanning_paused
        }

    def toggle_engine(self):
        """Toggles the live market signal scanner state between started and stopped."""
        self.engine.scanning_paused = not self.engine.scanning_paused
        is_active = not self.engine.scanning_paused
        logger.info(f"[TOOL] Signal scanner toggled: {'ACTIVE' if is_active else 'STOPPED'}")
        return {
            "success": True,
            "active": is_active,
            "paused": self.engine.scanning_paused
        }

    def get_advanced_filters_config(self):
        """Returns complete configuration states for the 4 institutional safeguards."""
        return {
            "news_calendar": self.engine.news_calendar.get_config(),
            "quant_ev": self.engine.quant_ev.get_config(),
            "risk_manager": self.engine.risk_manager.get_config(),
            "session_scheduler": self.engine.scheduler.get_config()
        }

    def update_advanced_filters_config(self, config: dict):
        """Dynamically updates configuration for any of the 4 institutional safeguards."""
        if not isinstance(config, dict):
            return {"success": False, "error": "Invalid configuration payload"}
        try:
            if "news_calendar" in config and isinstance(config["news_calendar"], dict):
                self.engine.news_calendar.configure(**config["news_calendar"])
            if "quant_ev" in config and isinstance(config["quant_ev"], dict):
                self.engine.quant_ev.configure(**config["quant_ev"])
            if "risk_manager" in config and isinstance(config["risk_manager"], dict):
                self.engine.risk_manager.configure(**config["risk_manager"])
            if "session_scheduler" in config and isinstance(config["session_scheduler"], dict):
                self.engine.scheduler.configure(**config["session_scheduler"])
            return {"success": True, "config": self.get_advanced_filters_config()}
        except Exception as e:
            logger.error(f"[CONFIG ERROR] Failed to update advanced filters: {e}")
            return {"success": False, "error": str(e)}

    def get_upcoming_news_events(self, limit: int = 6):
        """Returns list of upcoming macroeconomic news events."""
        return self.engine.news_calendar.get_upcoming_events(limit=int(limit))

    def get_risk_session_metrics(self):
        """Returns active risk management session telemetry and circuit breaker status."""
        return self.engine.risk_manager.get_session_metrics()

    def reset_daily_risk_session(self):
        """Resets daily trading risk session and clears circuit breakers."""
        self.engine.risk_manager.reset_session()
        return {"success": True, "metrics": self.get_risk_session_metrics()}

    def login_credentials(self, email, password):
        """Autofills credentials into the embedded in-app broker terminal."""
        if self._broker_wv and self._main_form:
            Action = self._Action or __import__('System', fromlist=['Action']).Action
            def do_autofill():
                try:
                    js = f"""
                    try {{
                        const em = document.querySelector('input[type="email"], input[name="email"]');
                        const pw = document.querySelector('input[type="password"], input[name="password"]');
                        if (em) {{ em.value = {json.dumps(email)}; em.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
                        if (pw) {{ pw.value = {json.dumps(password)}; pw.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
                        const btn = document.querySelector('button[type="submit"]');
                        if (btn) btn.click();
                    }} catch(e) {{}}
                    """
                    self._broker_wv.CoreWebView2.ExecuteScriptAsync(js)
                except Exception:
                    pass
            self._run_on_ui(do_autofill)
            return True

        # Fallback to embedded window if not yet docked
        def on_authenticated(token, cookies):
            self.engine.session_token = token
            self.engine.ws_client.session_token = token
            logger.info("[AUTH] Real credentials authenticated from embedded broker session.")
            self.engine.restart_ingestion()

        return auth_manager.launch_embedded_login(email=email, password=password, on_success_callback=on_authenticated, js_api=self)

    def login_google(self):
        """Navigates the embedded broker to Google OAuth or triggers embedded login."""
        if self._broker_wv and self._main_form:
            def do_google():
                try:
                    js = """
                    try {
                        const gBtn = document.querySelector('.social__item--google, a[href*="google"], button[data-social="google"]');
                        if (gBtn) gBtn.click();
                    } catch(e) {}
                    """
                    self._broker_wv.CoreWebView2.ExecuteScriptAsync(js)
                except Exception:
                    pass
            self._run_on_ui(do_google)
            return True

        def on_authenticated(token, cookies):
            self.engine.session_token = token
            self.engine.ws_client.session_token = token
            logger.info("[AUTH] Real Google OAuth authenticated from embedded broker session.")
            self.engine.restart_ingestion()

        return auth_manager.launch_embedded_login(on_success_callback=on_authenticated, js_api=self)

    def on_broker_frame(self, raw_data: str):
        """Processes real-time WebSocket frames streamed directly from embedded Quotex session."""
        try:
            if not hasattr(self, '_logged_broker_frame_count'):
                self._logged_broker_frame_count = 0
            if self._logged_broker_frame_count < 2 and raw_data:
                self._logged_broker_frame_count += 1
                logger.info(f"[BROKER FRAME SAMPLE] {raw_data[:120]}")
            self.engine.ws_client.process_raw_frame(raw_data)
            if not self.engine.ws_client.is_connected:
                self.engine.ws_client._connected = True
                self.engine.ws_client._update_status("connected", "Connected (Broker Linked)")
        except Exception as e:
            logger.debug(f"[FRAME BRIDGE] Error parsing broker frame: {e}")

    def on_broker_payouts(self, payouts: dict):
        """Processes dynamic payout percentages pushed from Quotex instruments array."""
        if not payouts:
            return
        now = time.time()
        self.engine.ws_client._last_heartbeat = now
        for sym, val in payouts.items():
            try:
                asset_registry.update_payout(sym, float(val))
            except Exception:
                pass
        if not hasattr(self, '_last_logged_payout_ts') or (now - self._last_logged_payout_ts > 15.0):
            self._last_logged_payout_ts = now
            logger.info(f"[LIVE PAYOUTS] Real-time broker payouts updated ({len(payouts)} assets active)")
        if not self.engine.ws_client.is_connected:
            self.engine.ws_client._connected = True
            self.engine.ws_client._update_status("connected", "Connected (Broker Linked)")

    def on_broker_instruments(self, instruments: list):
        """Processes dynamic instruments catalog pushed from Quotex instruments array."""
        if not instruments:
            return
        now = time.time()
        self.engine.ws_client._last_heartbeat = now
        registered_any = False
        for item in instruments:
            try:
                ws_asset = item.get("ws_asset")
                sym = item.get("symbol")
                cat = item.get("category", "currencies")
                prec = item.get("precision", 5)
                payout = item.get("payout")
                if ws_asset:
                    asset_registry.register_dynamic_asset(
                        ws_code=str(ws_asset),
                        display_name=str(sym) if sym else None,
                        category=str(cat),
                        precision=int(prec),
                        payout=float(payout) if payout is not None else None
                    )
                    registered_any = True
            except Exception as e:
                logger.debug(f"[INSTRUMENTS BRIDGE ERR] {e}")

        if registered_any:
            try:
                all_assets = asset_registry.get_all_asset_defs()
                self.engine.safe_emit_js(f"if (window.onAssetsUpdated) window.onAssetsUpdated({json.dumps(all_assets)});")
                logger.info(f"[DYNAMIC ASSETS] Catalog refreshed from Quotex ({len(all_assets)} total assets)")
            except Exception as e:
                logger.debug(f"[DYNAMIC ASSETS EMIT ERR] {e}")

        if not self.engine.ws_client.is_connected:
            self.engine.ws_client._connected = True
            self.engine.ws_client._update_status("connected", "Connected (Broker Linked)")

    def on_broker_candles(self, asset: str, data: list):
        """Bootstraps authentic historical candle series streamed directly from Quotex."""
        if not asset or not data:
            return
        try:
            display_symbol = asset_registry.ws_to_symbol(asset)
            if not display_symbol:
                if asset in asset_registry.get_all_symbols():
                    display_symbol = asset
                else:
                    return

            from core.ingester.frame_parser import extract_candles_from_payload
            _, parsed = extract_candles_from_payload("history", {"asset": asset, "candles": data})
            if parsed:
                candle_objects = [
                    Candle(
                        timestamp=int(c["time"]),
                        open=float(c["open"]),
                        high=float(c["high"]),
                        low=float(c["low"]),
                        close=float(c["close"]),
                        volume=float(c.get("volume", 100.0))
                    )
                    for c in parsed
                ]
                if len(candle_objects) >= 5:
                    self.engine.candle_store.bootstrap_history(display_symbol, candle_objects)
                    logger.info(f"[BROKER CANDLES] Bootstrapped {len(candle_objects)} authentic bars for {display_symbol}")
                    latest_price = float(candle_objects[-1].close)
                    self.on_broker_tick(display_symbol, latest_price, source="broker_history")

                    # Immediately synchronize UI Live Chart with authentic Quotex candles
                    try:
                        formatted_candles = [
                            {
                                "timestamp": int(c.timestamp),
                                "open": float(c.open),
                                "high": float(c.high),
                                "low": float(c.low),
                                "close": float(c.close),
                                "volume": float(c.volume),
                                "is_forming": False
                            }
                            for c in candle_objects
                        ]
                        payload_json = json.dumps({"symbol": display_symbol, "candles": formatted_candles})
                        self.engine.safe_emit_js(f"if (window.onHistoryBootstrapped) window.onHistoryBootstrapped({payload_json});")
                    except Exception as emit_err:
                        logger.debug(f"[BROKER CANDLES] Error emitting to UI: {emit_err}")
        except Exception as e:
            logger.debug(f"[BROKER CANDLES] Error processing candle history for {asset}: {e}")

    def on_broker_tick(self, symbol: str, price: float, source: str = "unknown"):
        """Processes live quotes captured directly from the active trade room."""
        try:
            now = time.time()
            self.engine.ws_client._last_heartbeat = now
            self.engine.ws_client._last_tick_time = now

            if not symbol or "," in symbol or any(k in symbol.lower() for k in ["put", "call", "bonus", "promo", "period"]):
                return

            price_f = float(price)
            if price_f <= 0.0001 or price_f in (1.0, 10.0, 50.0, 100.0):
                return

            display_symbol = asset_registry.ws_to_symbol(symbol)
            if not display_symbol:
                # Check if symbol is already a valid display symbol in registry
                if symbol in asset_registry.get_all_symbols():
                    display_symbol = symbol
                else:
                    return

            self._current_tick_source = source

            # Plausibility check against last known good price
            last_price = asset_registry.get_latest_price(display_symbol)
            if last_price and last_price > 0:
                pct_diff = abs(price_f - last_price) / last_price
                # Tune per asset class: FX OTC pairs move far less than Crypto pairs
                is_crypto = any(c in display_symbol.upper() for c in ["BTC", "ETH", "SOL", "XRP"])
                threshold = 0.20 if is_crypto else 0.03
                if pct_diff > threshold:
                    if not hasattr(self, '_tick_rejection_counts'):
                        self._tick_rejection_counts = {}
                    rej_count = self._tick_rejection_counts.get(display_symbol, 0) + 1
                    self._tick_rejection_counts[display_symbol] = rej_count
                    if rej_count < 3:
                        logger.warning(
                            f"[TICK SANITY] Rejected implausible tick for {display_symbol}: "
                            f"{price_f} vs last known {last_price} ({pct_diff:.1%} jump) "
                            f"from source={source}"
                        )
                        return
                    else:
                        logger.info(
                            f"[TICK SANITY] Accepted confirmed shifted price for {display_symbol}: "
                            f"{price_f} after {rej_count} confirming ticks."
                        )
                        self._tick_rejection_counts[display_symbol] = 0
                elif hasattr(self, '_tick_rejection_counts') and display_symbol in self._tick_rejection_counts:
                    self._tick_rejection_counts[display_symbol] = 0

            asset_registry.update_latest_price(display_symbol, price_f, source=source)

            if not hasattr(self, '_last_logged_tick'):
                self._last_logged_tick = {}
            if now - self._last_logged_tick.get(display_symbol, 0.0) > 10.0:
                self._last_logged_tick[display_symbol] = now
                logger.info(f"[LIVE TICK] {display_symbol} @ {price_f} (source={source})")

            if self.engine.ws_client.on_tick:
                try:
                    self.engine.ws_client.on_tick(display_symbol, price_f, source=source)
                except TypeError:
                    self.engine.ws_client.on_tick(display_symbol, price_f)
            # Accumulate in CandleStore to build candles and fire indicator strategy signals
            completed_bar = self.engine.candle_store.add_tick(display_symbol, price_f)
            if completed_bar and self.engine.ws_client.on_candle:
                self.engine.ws_client.on_candle(display_symbol, completed_bar)
            if not self.engine.ws_client.is_connected:
                self.engine.ws_client._connected = True
                self.engine.ws_client._update_status("connected", "Connected (Broker Linked)")
        except Exception as e:
            logger.warning(f"[BROKER TICK] Error processing tick: {e}")

    def switch_pair(self, symbol: str):
        """Switches the embedded Quotex broker chart to the selected currency pair."""
        logger.info(f"[SWITCH PAIR] Requested switch to {symbol}")
        if not symbol:
            return {"success": False, "error": "No symbol provided"}

        ws_code = asset_registry.symbol_to_ws(symbol) or symbol
        if self._broker_wv and self._main_form:
            def do_switch():
                try:
                    js = f"""
                    (async () => {{
                        try {{
                            if (window.__tp_switch_pair) {{
                                return await window.__tp_switch_pair({json.dumps(ws_code)}, {json.dumps(symbol)});
                            }}
                        }} catch (e) {{
                            console.warn('[SWITCH PAIR] Error:', e);
                        }}
                    }})();
                    """
                    self._broker_wv.CoreWebView2.ExecuteScriptAsync(js)
                except Exception as e:
                    logger.debug(f"[SWITCH PAIR] Script execution error: {e}")
            self._run_on_ui(do_switch)
            return {"success": True, "symbol": symbol, "ws_code": ws_code}
        return {"success": False, "error": "Broker window not initialized"}

    def prime_asset_stream(self, symbol: str):
        """Directly activates real-time streaming for an unstreamed asset without user interaction."""
        if not symbol:
            return {"success": False, "error": "No symbol provided"}
        ws_code = asset_registry.symbol_to_ws(symbol) or symbol
        if self._broker_wv and self._main_form:
            def do_prime():
                try:
                    js = f"""
                    (() => {{
                        try {{
                            if (window.__tp_prime_asset) {{
                                window.__tp_prime_asset({json.dumps(ws_code)});
                            }}
                        }} catch (e) {{}}
                    }})();
                    """
                    self._broker_wv.CoreWebView2.ExecuteScriptAsync(js)
                except Exception as e:
                    logger.debug(f"[PRIME ASSET] Script execution error: {e}")
            self._run_on_ui(do_prime)
            return {"success": True, "symbol": symbol, "ws_code": ws_code}
        return {"success": False, "error": "Broker window not initialized"}

    def _start_auto_primer(self):
        """Background thread that automatically primes all watched pairs until live rates arrive."""
        if self._auto_primer_started:
            return
        self._auto_primer_started = True

        def primer_worker():
            import time as _pytime
            # Allow embedded WebView2 and Quotex WebSocket to complete initial handshake
            _pytime.sleep(3.0)
            while self.engine.running:
                _pytime.sleep(1.0)
                try:
                    if not self._broker_wv or not self._main_form:
                        continue
                    if not self.engine.ws_client.is_connected:
                        continue

                    all_syms = asset_registry.get_all_symbols()
                    unstreamed = [
                        s for s in all_syms
                        if s not in self.engine.unwatched_symbols
                        and (
                            asset_registry.get_latest_price(s) is None
                            or asset_registry.get_latest_price(s) <= 0.0001
                            or not self.engine.candle_store.has_sufficient_history(s, min_bars=25)
                        )
                    ]

                    if unstreamed:
                        # Prime up to 2 unstreamed assets smoothly
                        for sym in unstreamed[:2]:
                            self.prime_asset_stream(sym)
                            _pytime.sleep(0.3)
                except Exception as ex:
                    logger.debug(f"[AUTO PRIMER] Worker note: {ex}")

        threading.Thread(target=primer_worker, daemon=True, name="TradePulse-AutoPrimer").start()

    def show_broker_window(self):
        """Switches directly to the Quotex terminal view in the main window."""
        if self._webview_window:
            try:
                self._webview_window.evaluate_js("switchView('broker');")
                return True
            except Exception:
                pass
        return False

    def run_quick_backtest(self, strategy_id):
        strat = strategy_manager.get_strategy(strategy_id)
        if not strat:
            return {"error": "Strategy not found"}

        # Use EUR/USD (OTC) or USD/INR (OTC) as reference asset for quick backtest
        sample_sym = "USD/INR (OTC)"
        candles = self.engine.candle_store.get_candles(sample_sym, "1M", contiguous_only=False)
        if len(candles) < 25:
            try:
                from core.storage.db import db
                db_bars = db.get_recent_candles(sample_sym, 300)
                if len(db_bars) >= 25:
                    candles = db_bars
            except Exception:
                pass
        if len(candles) < 25:
            sample_sym = "EUR/USD (OTC)"
            candles = self.engine.candle_store.get_candles(sample_sym, "1M", contiguous_only=False)
            if len(candles) < 25:
                try:
                    from core.storage.db import db
                    db_bars = db.get_recent_candles(sample_sym, 300)
                    if len(db_bars) >= 25:
                        candles = db_bars
                except Exception:
                    pass

        candles_5m = self.engine.candle_store._synthesize_timeframe(candles, 300) if len(candles) >= 5 else []
        return HistoricalBacktestEngine.test_strategy_on_asset(strat, candles, candles_5m)

    def run_backtest(self, strategy_id):
        """Alias for run_quick_backtest to match frontend API calls."""
        return self.run_quick_backtest(strategy_id)

    def toggle_asset_watch(self, symbol: str, is_watched: bool):
        if is_watched:
            self.engine.unwatched_symbols.discard(symbol)
        else:
            self.engine.unwatched_symbols.add(symbol)
        return True

    def clear_session(self):
        auth_manager.clear_session()
        self.engine.session_token = None
        self.engine.ws_client.session_token = None
        self.engine.ws_client.stop()
        return True

    def set_global_cooldown(self, seconds: int):
        """Updates the overarching cooldown period across all strategies."""
        try:
            sec_val = max(10, int(seconds))
            cooldown_manager.set_global_cooldown(sec_val)
            logger.info(f"[CONFIG] Global signal cooldown set to {sec_val}s")
            return {"success": True, "cooldown": sec_val}
        except Exception as e:
            logger.warning(f"[CONFIG] Error setting cooldown: {e}")
            return {"success": False, "error": str(e)}

    def save_telegram_config(self, token: str, chat_id: str, send_charts: bool = True):
        token = (token or "").strip()
        chat_id = (chat_id or "").strip()
        settings.TELEGRAM_BOT_TOKEN = token
        settings.TELEGRAM_CHAT_IDS = chat_id

        # Update running telegram bridge
        self.engine.telegram.token = token
        self.engine.telegram.api_base = f"https://api.telegram.org/bot{token}" if token else ""
        self.engine.telegram.subscribers = {c.strip() for c in chat_id.split(",") if c.strip()}

        # Persist to .env file in root/exe directory
        if getattr(sys, "frozen", False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).resolve().parent
        env_file = app_dir / ".env"
        try:
            lines = []
            if env_file.exists():
                lines = env_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            token_set, chat_set = False, False
            for line in lines:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
                    token_set = True
                elif line.startswith("TELEGRAM_CHAT_IDS="):
                    new_lines.append(f"TELEGRAM_CHAT_IDS={chat_id}")
                    chat_set = True
                else:
                    new_lines.append(line)
            if not token_set:
                new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
            if not chat_set:
                new_lines.append(f"TELEGRAM_CHAT_IDS={chat_id}")
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[CONFIG] Failed to write .env: {e}")

        # Restart telegram background client
        if self.engine._loop and self.engine._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._restart_telegram(), self.engine._loop)

        return {"success": True, "message": "Telegram VIP Bot settings saved & active!"}

    async def _restart_telegram(self):
        self.engine.telegram.stop()
        await asyncio.sleep(0.5)
        self.engine.telegram.start()

    def test_telegram(self):
        """Sends test VIP alert using active Telegram Manager or settings credentials."""
        token = self.engine.telegram_manager.bot_token or settings.TELEGRAM_BOT_TOKEN
        channels = self.engine.telegram_manager.channels
        if channels:
            target = channels[0].get("id")
        else:
            cids = settings.chat_id_list
            target = cids[0] if cids else ""

        if not token or not target:
            return False
        res = self.send_test_telegram(token, target, send_charts=True)
        return res.get("success", False)

    def send_test_telegram(self, token: str, chat_id: str, send_charts: bool = True):
        token = (token or "").strip()
        chat_id = (chat_id or "").strip()
        if not token or not chat_id:
            return {"error": "Please enter both Telegram Bot Token and Chat ID."}

        import httpx
        try:
            target_chat = chat_id.split(",")[0].strip()
            msg = (
                "⚡ <b>TRADEPULSE — VIP TEST BROADCAST</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ <b>Telegram VIP Signal Channel Connected!</b>\n\n"
                "• <b>Status:</b> Active & Listening\n"
                "• <b>Format:</b> High-Precision HTML Cards\n"
                "• <b>HD Charts:</b> Enabled\n"
                "• <b>Target Chat:</b> <code>" + target_chat + "</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🎯 <i>Real-time OTC signals will be dispatched here.</i>"
            )
            resp = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": target_chat,
                    "text": msg,
                    "parse_mode": "HTML"
                },
                timeout=10.0
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {"success": True, "message": f"Test signal sent successfully to {target_chat}!"}
            else:
                err_desc = data.get("description", resp.text)
                return {"error": f"Telegram API Error ({resp.status_code}): {err_desc}"}
        except Exception as e:
            return {"error": f"Connection Error: {e}"}

    def send_test_rendered_template(self, template_key: str, template_text: str):
        """Dispatches an authentic rendered test sample of the template to the user's primary channel."""
        token = self.engine.telegram_manager.bot_token or settings.TELEGRAM_BOT_TOKEN
        channels = self.engine.telegram_manager.channels
        if channels:
            target = channels[0].get("id")
        else:
            cids = settings.chat_id_list
            target = cids[0] if cids else ""

        if not token or not target:
            return {"success": False, "error": "Please enter Telegram Bot Token and add a Channel first."}

        prev = self.preview_telegram_template(template_key, template_text)
        rendered_msg = prev.get("rendered") if prev.get("success") else template_text

        import httpx
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": target,
                    "text": rendered_msg,
                    "parse_mode": "HTML"
                },
                timeout=10.0
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {"success": True, "message": f"Test card sent to Telegram channel ({target})!"}
            else:
                return {"success": False, "error": data.get("description", "Failed to send message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_feature_toggles(self):
        """Returns active configuration toggles for OTC Guard, Pre-Alerts, Voice, and Confluence."""
        return {
            "otc_flatline_guard": getattr(settings, "OTC_FLATLINE_GUARD", True),
            "pre_alerts": getattr(settings, "PRE_ALERTS_ENABLED", True),
            "voice_alerts": getattr(settings, "VOICE_ALERTS_ENABLED", True),
            "confluence_scanner": getattr(settings, "CONFLUENCE_SCANNER_ENABLED", True),
            "global_cooldown": cooldown_manager.global_cooldown_seconds
        }

    def update_feature_toggle(self, name: str, enabled: bool):
        """Toggles an advanced feature on or off dynamically."""
        key_map = {
            "otc_flatline_guard": "OTC_FLATLINE_GUARD",
            "pre_alerts": "PRE_ALERTS_ENABLED",
            "voice_alerts": "VOICE_ALERTS_ENABLED",
            "confluence_scanner": "CONFLUENCE_SCANNER_ENABLED"
        }
        attr_name = key_map.get(name.lower())
        if attr_name:
            setattr(settings, attr_name, bool(enabled))
            logger.info(f"[FEATURE TOGGLE] {attr_name} set to {enabled}")
            return {"success": True, "name": name, "enabled": bool(enabled)}
        return {"success": False, "error": f"Unknown toggle: {name}"}

    def get_performance_stats(self):
        """Returns live session win rate, strategy performance breakdown, and top pairs."""
        return db.get_performance_stats()

    def get_signals_history(self, limit: int = 100):
        """Returns recent signals audit trail from SQLite database."""
        try:
            return list(db.get_recent_signals(limit))
        except Exception as e:
            logger.debug(f"[API ERROR] get_signals_history: {e}")
            return []

    def get_candles_for_chart(self, symbol: str, timeframe: str = "1M"):
        """Returns recent chronological candlestick history formatted for interactive charting."""
        if not symbol:
            return []
        from core.models.candle import Candle
        # 1. Retrieve all chronological session bars from rolling buffer
        candles = self.engine.candle_store.get_candles(symbol, timeframe, contiguous_only=False)
        if len(candles) < 40:
            # Trigger background broker history load if buffer is sparse
            try:
                self.prime_asset_stream(symbol)
            except Exception:
                pass
            try:
                from core.storage.db import db
                db_bars = db.get_recent_candles(symbol, 200)
                if db_bars:
                    # Filter db_bars to active contiguous tail only (no ancient session stitching)
                    contig_db = []
                    for b in reversed(db_bars):
                        if not contig_db:
                            contig_db.append(b)
                        else:
                            gap = contig_db[-1].timestamp - b.timestamp
                            if gap <= 0:
                                continue
                            # Accept all bars regardless of gap size — frontend handles visual continuity
                            contig_db.append(b)
                    contig_db.reverse()
                    if len(contig_db) > len(candles):
                        tf_upper = timeframe.upper()
                        if tf_upper in ["1M", "1MIN", "60"]:
                            candles = contig_db
                        else:
                            tf_sec = 180 if "3M" in tf_upper else (300 if "5M" in tf_upper else (900 if "15M" in tf_upper else 60))
                            candles = self.engine.candle_store._synthesize_timeframe(contig_db, tf_sec)
            except Exception:
                pass

        # 2. Fill any minor 1-5 minute lulls within the continuous session
        continuous_bars = []
        for c in candles:
            if not continuous_bars:
                continuous_bars.append(c)
                continue
            prev_c = continuous_bars[-1]
            gap_sec = c.timestamp - prev_c.timestamp
            if gap_sec <= 0:
                continue
            if 60 < gap_sec <= 120:
                for fill_ts in range(prev_c.timestamp + 60, c.timestamp, 60):
                    continuous_bars.append(Candle(
                        timestamp=fill_ts,
                        open=prev_c.close,
                        high=prev_c.close,
                        low=prev_c.close,
                        close=prev_c.close,
                        volume=0.0
                    ))
            # For gaps > 120s: simply append without fabricating flatlines.
            # Preserves all historical bars for chart scrollback.
            continuous_bars.append(c)

        formatted = [
            {
                "timestamp": int(c.timestamp),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            }
            for c in continuous_bars[-200:]
            if getattr(c, 'timestamp', 0) >= 1000000000 and c.open > 0 and c.close > 0
        ]
        formatted.sort(key=lambda x: x["timestamp"])

        tf_upper = timeframe.upper()
        if tf_upper in ["1M", "1MIN", "60"]:
            try:
                acc = self.engine.candle_store._accumulators.get(symbol)
                if acc and acc.get("minute", 0) >= 1000000000 and acc.get("close", 0) > 0:
                    acc_min = int(acc["minute"])
                    if not formatted:
                        formatted.append({
                            "timestamp": acc_min,
                            "open": float(acc["open"]),
                            "high": float(acc["high"]),
                            "low": float(acc["low"]),
                            "close": float(acc["close"]),
                            "volume": float(acc.get("ticks", 1) * 100),
                            "is_forming": True
                        })
                    elif acc_min > formatted[-1]["timestamp"]:
                        prev_bar = formatted[-1]
                        gap_to_acc = acc_min - prev_bar["timestamp"]
                        if 60 < gap_to_acc <= 120:
                            for fill_ts in range(prev_bar["timestamp"] + 60, acc_min, 60):
                                formatted.append({
                                    "timestamp": fill_ts,
                                    "open": prev_bar["close"],
                                    "high": prev_bar["close"],
                                    "low": prev_bar["close"],
                                    "close": prev_bar["close"],
                                    "volume": 0.0,
                                    "is_forming": False
                                })
                        new_open = float(formatted[-1]["close"]) if gap_to_acc <= 120 else float(acc["open"])
                        formatted.append({
                            "timestamp": acc_min,
                            "open": new_open,
                            "high": max(new_open, float(acc["high"])),
                            "low": min(new_open, float(acc["low"])),
                            "close": float(acc["close"]),
                            "volume": float(acc.get("ticks", 1) * 100),
                            "is_forming": True
                        })
                    elif acc_min == formatted[-1]["timestamp"]:
                        last_bar = formatted[-1]
                        last_bar["high"] = max(last_bar["high"], float(acc["high"]))
                        last_bar["low"] = min(last_bar["low"], float(acc["low"]))
                        last_bar["close"] = float(acc["close"])
                        last_bar["is_forming"] = True
            except Exception:
                pass
        else:
            # Multi-timeframe active forming candle synthesis
            try:
                tf_sec = 180 if "3M" in tf_upper else (300 if "5M" in tf_upper else (900 if "15M" in tf_upper else 60))
                now_sec = int(time.time())
                curr_boundary = (now_sec // tf_sec) * tf_sec
                raw_1m = self.engine.candle_store.get_candles(symbol, "1M", contiguous_only=True)
                bucket_bars = [b for b in raw_1m if (b.timestamp // tf_sec) * tf_sec == curr_boundary and b.open > 0]
                acc = self.engine.candle_store._accumulators.get(symbol)
                if acc and (acc.get("minute", 0) // tf_sec) * tf_sec == curr_boundary and acc.get("close", 0) > 0:
                    bucket_bars.append(Candle(
                        timestamp=int(acc["minute"]),
                        open=float(acc["open"]),
                        high=float(acc["high"]),
                        low=float(acc["low"]),
                        close=float(acc["close"]),
                        volume=float(acc.get("ticks", 1) * 100)
                    ))
                if bucket_bars:
                    forming_bar = {
                        "timestamp": curr_boundary,
                        "open": float(bucket_bars[0].open),
                        "high": float(max(b.high for b in bucket_bars)),
                        "low": float(min(b.low for b in bucket_bars)),
                        "close": float(bucket_bars[-1].close),
                        "volume": float(sum(b.volume for b in bucket_bars)),
                        "is_forming": True
                    }
                    if not formatted or curr_boundary > formatted[-1]["timestamp"]:
                        formatted.append(forming_bar)
                    elif curr_boundary == formatted[-1]["timestamp"]:
                        formatted[-1] = forming_bar
            except Exception:
                pass

        return formatted

    def set_app_muted(self, is_muted: bool):
        """Mutes or unmutes both the main window and embedded broker WebView2 controls."""
        logger.info(f"[AUDIO] Application master mute state set to: {is_muted}")
        try:
            # 1. Mute embedded broker WebView2 if active
            broker_wv = getattr(self.engine, '_broker_wv', None)
            if broker_wv and hasattr(broker_wv, 'CoreWebView2') and broker_wv.CoreWebView2:
                broker_wv.CoreWebView2.IsMuted = bool(is_muted)
        except Exception as e:
            logger.debug(f"[AUDIO] Broker WebView2 mute error: {e}")

        try:
            # 2. Mute main pywebview window CoreWebView2 if present
            main_wv = getattr(self.engine, '_wv', None)
            if main_wv and hasattr(main_wv, 'CoreWebView2') and main_wv.CoreWebView2:
                main_wv.CoreWebView2.IsMuted = bool(is_muted)
        except Exception as e:
            logger.debug(f"[AUDIO] Main WebView2 mute error: {e}")
        return {"success": True, "is_muted": bool(is_muted)}

    # -------------------------------------------------------------------------
    # Telegram Manager & Template Customization API
    # -------------------------------------------------------------------------

    def get_telegram_manager_state(self):
        """Returns the full Telegram manager configuration including templates, channels, and rules."""
        return self.engine.telegram_manager.get_config()

    def update_telegram_manager_config(self, new_config: Dict[str, Any]):
        """Persists updated Telegram manager settings, channels, rules, and templates."""
        try:
            updated = self.engine.telegram_manager.update_config(new_config)
            # Synchronize tracker lock settings with telegram manager rules
            if hasattr(self.engine, 'tracker') and self.engine.tracker:
                self.engine.tracker.sequential_trade_lock = self.engine.telegram_manager.sequential_trade_lock
                self.engine.tracker.loss_cooldown_seconds = self.engine.telegram_manager.loss_cooldown_seconds
            # Update active bridge credentials in memory if bot_token changed
            new_token = updated.get("bot_token")
            if new_token:
                self.engine.telegram.token = new_token
                self.engine.telegram.api_base = f"https://api.telegram.org/bot{new_token}"
            # Update subscribers set from enabled channels
            active_channels = [c.get("id") for c in updated.get("channels", []) if c.get("id") and c.get("enabled", True)]
            if active_channels:
                self.engine.telegram.subscribers = set(active_channels)
            # Hot-restart background client ONLY if connection credentials/channels changed
            if "bot_token" in new_config or "channels" in new_config or "polling_enabled" in new_config:
                if self.engine._loop and self.engine._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._restart_telegram(), self.engine._loop)
            return {"success": True, "config": updated}
        except Exception as e:
            logger.error(f"[TELEGRAM MANAGER CONFIG ERROR] {e}", exc_info=True)
            return {"success": False, "error": str(e), "config": self.engine.telegram_manager.get_config()}

    def save_telegram_template(self, template_key: str, template_text: str):
        """Persists a specific Telegram template directly to disk."""
        try:
            ok = self.engine.telegram_manager.set_template(template_key, template_text)
            if ok:
                return {
                    "success": True,
                    "template_key": template_key,
                    "template": self.engine.telegram_manager.get_template(template_key),
                    "config": self.engine.telegram_manager.get_config()
                }
            return {"success": False, "error": f"Invalid template key or empty content for '{template_key}'"}
        except Exception as e:
            logger.error(f"[TELEGRAM TEMPLATE SAVE ERROR] {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def test_telegram_bot_token(self, token: Optional[str] = None):
        """Verifies Telegram bot token validity via getMe."""
        try:
            res = self.engine.telegram.verify_bot_token(token)
            if not isinstance(res, dict):
                return {"ok": False, "valid": False, "error": "Invalid response"}
            return res
        except Exception as e:
            return {"ok": False, "valid": False, "error": str(e)}

    def test_send_telegram_channel(self, channel_id: str, custom_msg: Optional[str] = None):
        """Sends a verification ping or custom message to a specific Telegram channel."""
        text = custom_msg or "🔔 <b>TradePulse Test Ping</b>\n<i>Your channel connection is operational!</i>"
        if not self.engine._loop:
            return {"success": False, "error": "Event loop not running"}
        fut = asyncio.run_coroutine_threadsafe(
            self.engine.telegram.broadcast_custom_message(text=text, target_chat_id=channel_id),
            self.engine._loop
        )
        try:
            res = fut.result(timeout=10.0)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def broadcast_custom_telegram_message(self, text: str, target_chat_id: Optional[str] = None):
        """Broadcasts a manual announcement or custom message to configured channels."""
        if not text or not text.strip():
            return {"success": False, "error": "Message content cannot be empty"}
        if not self.engine._loop:
            return {"success": False, "error": "Event loop not running"}
        fut = asyncio.run_coroutine_threadsafe(
            self.engine.telegram.broadcast_custom_message(text=text.strip(), target_chat_id=target_chat_id),
            self.engine._loop
        )
        try:
            res = fut.result(timeout=10.0)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_telegram_template(self, template_key: str):
        """Resets the specified message template back to default."""
        res = self.engine.telegram_manager.reset_template_to_default(template_key)
        return {"success": True, "template_key": template_key, "template": res}

    def preview_telegram_template(self, template_key: str, template_text: str):
        """Renders a live sample preview of a template given current token text."""
        ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%H:%M:%S")
        expiry_now = (datetime.now(timezone(timedelta(hours=5, minutes=30))) + timedelta(minutes=1)).strftime("%H:%M:%S")
        context = {
            "asset": "EUR/USD (OTC)",
            "direction": "CALL",
            "dir_badge": "CALL (UP) 🟢",
            "arrow": "📈",
            "payout": "92%",
            "confidence": "94",
            "tier": "MAX CONFLUENCE",
            "strategy": "Engulfing Breakout Momentum",
            "timeframe": "1M",
            "duration": "1",
            "expiry": "1",
            "expiry_minutes": "1",
            "entry_time": ist_now,
            "expiry_time": expiry_now,
            "entry_price": "1.08542",
            "exit_price": "1.08560",
            "rec_stake": "$25.00",
            "martingale_step": "1",
            "stake_line": "💰 <b>Recommended Stake:</b> <b>$25.00 (Step 1)</b>\n",
            "ev_edge": "+$8.28",
            "ev_line": "🧮 <b>Quant Edge:</b> <b>EV +$8.28</b>\n",
            "confluence_section": "🤝 <b>Confirming:</b> <b>MTF Trend + RSI Oversold</b>\n",
            "status": "WIN",
            "outcome_badge": "WIN ✅",
            "pnl_text": "💰 <b>Profit:</b> <b>+92% Return</b>",
            "remaining_seconds": "18",
            "cb_reason": "Daily Max Loss Threshold (-$150.00)",
            "net_pnl": "-$152.50",
            "win_rate": "54.2%",
            "total_trades": "24",
            "header": "⚡ <b>VIP SIGNAL ALERT</b>" if template_key == "signal" else "⚡ <b>PRE-SIGNAL RADAR</b>"
        }
        rendered = TelegramManager.interpolate(template_text, context)
        return {"success": True, "rendered": rendered, "context": context}



# -----------------------------------------------------------------------------
# Runtime Launchers: Desktop GUI vs Headless VPS Daemon
# -----------------------------------------------------------------------------

def run_desktop_app(engine: TradePulseEngine):
    """Launches the modern PyWebView desktop interface."""
    import webview

    api = TradePulseBridgeAPI(engine)
    engine.set_bridge_api(api)
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base_dir = Path(__file__).resolve().parent
    ui_dir = base_dir / "ui"
    index_html = (ui_dir / "index.html").as_uri()

    window = webview.create_window(
        title="TradePulse — OTC Signal Station",
        url=index_html,
        js_api=api,
        width=1320,
        height=840,
        min_size=(960, 640),
        background_color="#0b0e14",
        easy_drag=False
    )
    api._main_win = window
    engine.set_webview_window(window)

    def on_started():
        def init_worker():
            import time
            from webview.platforms.winforms import BrowserView
            for attempt in range(60):
                form = BrowserView.instances.get(window.uid)
                if form and getattr(form, 'IsHandleCreated', False):
                    api._main_form = form
                    logger.info(f"[STARTUP] WinForms handle ready on attempt {attempt + 1}. Initializing embedded broker...")
                    api.init_embedded_broker()
                    return
                time.sleep(0.1)
            logger.warning("[STARTUP] Timeout waiting for WinForms handle. Attempting fallback init...")
            api._main_form = BrowserView.instances.get(window.uid)
            api.init_embedded_broker()

        threading.Thread(target=init_worker, daemon=True).start()

    webview.start(on_started, debug=False)


async def run_headless_daemon(engine: TradePulseEngine):
    """Runs 24/7 background daemon on Linux/Ubuntu VPS."""
    logger.info("==========================================================")
    logger.info("⚡ TradePulse 24/7 Headless VPS Daemon Online")
    logger.info("==========================================================")
    while True:
        await asyncio.sleep(3600)


def main():
    ensure_single_instance()
    parser = argparse.ArgumentParser(description="TradePulse Real-Time Signal Platform")
    parser.add_argument("--headless", action="store_true", help="Force headless VPS daemon mode (no GUI)")
    args = parser.parse_args()

    # Automatic Headless Detection (e.g. Linux servers without X11 DISPLAY)
    is_headless = args.headless or (platform.system() == "Linux" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"))

    engine = TradePulseEngine()

    if is_headless:
        logger.info("[MODE] Operating in 24/7 Headless VPS Daemon Mode.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        engine.set_loop(loop)
        loop.call_soon(engine.start)
        try:
            loop.run_until_complete(run_headless_daemon(engine))
        except (KeyboardInterrupt, SystemExit):
            engine.stop()
    else:
        logger.info("[MODE] Operating in Desktop GUI Mode.")
        # Start core background async loop in dedicated daemon thread
        def start_background_loop(loop):
            asyncio.set_event_loop(loop)
            engine.set_loop(loop)
            loop.call_soon(engine.start)
            loop.run_forever()

        bg_loop = asyncio.new_event_loop()
        t = threading.Thread(target=start_background_loop, args=(bg_loop,), daemon=True)
        t.start()

        # Launch PyWebView desktop GUI on main thread
        run_desktop_app(engine)
        engine.stop()


if __name__ == "__main__":
    main()
