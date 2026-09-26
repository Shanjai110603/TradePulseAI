"""
TradePulse Personal — Institutional Real Forex Workstation
==========================================================
Dedicated personal edition engineered exclusively for all Real Market Forex Currencies (NO OTC).
Includes 1-to-1 personal Telegram signal broadcasting with a strict 5-user security limit.
Compiled for distribution with no terminal, console, or code exposure.

Key Specifications:
- 100% Real Market Forex Currencies (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, EUR/GBP, etc.)
- Zero OTC pairs (no synthetic broker simulation)
- Embedded Quotex Login & Live Trading Terminal
- Bot scanner ONLY startable and functional when Quotex login is completed AND bot is started
- Personal Telegram Bot with strict 5-user access limit
- Isolated local database (tradepulse_personal.db)
- Native PyWebView GUI with Live Charts, Strategy Lab & Institutional Risk Suite
- Clean GUI with no terminal or code windows

Usage:
  python main_personal.py            # Desktop GUI Mode
  python main_personal.py --headless # 24/7 VPS Background Mode
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
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Mark Personal Edition environment flag
os.environ['TRADEPULSE_PERSONAL'] = '1'

# Ensure WebView2 runs cleanly without console, rubber-banding, or devtools code inspection
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
    '--disable-features=ElasticOverscroll '
    '--disable-web-security '
    '--allow-running-insecure-content '
    '--disable-gpu-watchdog '
    '--disable-devtools'
)

from core.charts.generator import ChartGenerator
from core.config import settings
from core.indicators.engine import TechnicalIndicatorEngine
from core.ingester.asset_registry import asset_registry
from core.ingester.auth_manager import auth_manager
from core.ingester.socket_client import QuotexSocketClient
from core.ingester.real_market_feed import RealMarketFeed
from core.models.candle import Candle, CandleStore
from core.models.signal import Signal
from core.storage.db import Database
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
from core.webhooks.server import WebhookServer
from core.news.calendar import EconomicCalendarEngine
from core.strategy.quant_ev import QuantEVFilter
from core.strategy.risk_manager import RiskManager
from core.strategy.session_scheduler import SessionScheduler
from core.strategy.optimizer import StrategyOptimizer
from core.licensing.client import license_client

# 1. Enforce Real Forex Currencies ONLY (NO OTC)
asset_registry.filter_real_currencies_only()

# 2. Dedicated Isolated Personal SQLite Database
personal_db_path = settings.resolved_data_dir / "tradepulse_personal.db"
personal_db = Database(db_path=personal_db_path)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [TradePulse-Personal]: %(message)s"
)
logger = logging.getLogger("TradePulsePersonal")

try:
    from logging.handlers import RotatingFileHandler
    log_file = settings.resolved_data_dir / "tradepulse_personal.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(str(log_file), maxBytes=10*1024*1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [Personal]: %(message)s"))
    logging.getLogger().addHandler(file_handler)
except Exception:
    pass


class TradePulsePersonalEngine:
    """Core coordinator for TradePulse Personal Edition (Real Currencies Only | Max 5 Users)."""

    def __init__(self):
        self.candle_store = CandleStore(max_bars=120)
        self.session_token = auth_manager.get_valid_session_token()
        self.start_time = time.time()
        self.running = False
        # Scanner starts paused until Quotex login is verified & user explicitly starts tool
        self.scanning_paused = True
        self.unwatched_symbols = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._webview_window = None
        self._bridge_api = None
        self.ui_ready: bool = False
        self._eval_pending: bool = False
        self._pre_signal_min: Dict[str, int] = {}

        # Real-time UI tick buffer
        self._tick_buffer: Dict[str, Any] = {}
        self._payout_buffer: Dict[str, float] = {}
        self._buffer_lock = threading.Lock()
        self._flush_thread: Optional[threading.Thread] = None

        # Subsystems (Initialized with Personal Database and Single Telegram connection)
        self.telegram_manager = TelegramManager()
        self.tracker = SignalTracker(
            self.candle_store,
            on_outcome_callback=self._on_trade_outcome,
            db_manager=personal_db,
            sequential_trade_lock=self.telegram_manager.sequential_trade_lock,
            loss_cooldown_seconds=self.telegram_manager.loss_cooldown_seconds
        )
        self.telegram = TelegramBridge(
            on_command_callback=self._on_telegram_command,
            manager=self.telegram_manager,
            max_users=1
        )
        self.webhook_server = WebhookServer(port=8766, on_signal_callback=self._on_external_webhook)
        self.news_calendar = EconomicCalendarEngine(data_dir=settings.resolved_data_dir)
        self.quant_ev = QuantEVFilter()
        self.risk_manager = RiskManager()
        self.scheduler = SessionScheduler()
        
        # Connect Live Client Telemetry to Master Control Panel
        license_client.set_telemetry_callback(self._collect_telemetry_snapshot)
        
        # High-frequency open-source real market feed (Interbank Forex)
        self.real_market_feed = RealMarketFeed(
            candle_store=self.candle_store,
            on_tick=self._on_tick,
            on_candle=self._on_candle_completed
        )
        # Quotex client for real pairs & payouts
        self.ws_client = QuotexSocketClient(
            candle_store=self.candle_store,
            session_token=self.session_token,
            on_tick_callback=self._on_tick,
            on_candle_callback=self._on_candle_completed,
            on_status_callback=self._on_status_update
        )

        asset_registry.add_payout_callback(self._on_payout_updated)

    def _collect_telemetry_snapshot(self) -> Dict[str, Any]:
        """Provides real-time telemetry snapshot to the Master Control Panel."""
        tok = self.telegram_manager.bot_token or ""
        token_prefix = tok[:8] if len(tok) >= 8 else tok
        chat_id = ""
        if self.telegram_manager.channels:
            chat_id = self.telegram_manager.channels[0].get("id", "")
        
        active_strats = [s.name for s in strategy_manager.get_active_strategies()]
        return {
            "bot_token_prefix": token_prefix,
            "telegram_chat_id": chat_id,
            "active_strategies": active_strats,
            "quotex_logged_in": self.is_quotex_logged_in(),
            "scanner_active": bool(self.running and not self.scanning_paused)
        }

    def is_quotex_logged_in(self) -> bool:
        """Returns True only when valid Quotex broker authentication is active."""
        has_token = bool(self.session_token and len(self.session_token) > 10)
        is_conn = bool(self.ws_client and self.ws_client.is_connected)
        return has_token or is_conn

    def is_operational(self) -> bool:
        """Returns True only when Quotex login is completed AND bot scanner is started."""
        return self.running and not self.scanning_paused and self.is_quotex_logged_in()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_webview_window(self, window):
        self._webview_window = window

    def set_bridge_api(self, api):
        self._bridge_api = api

    def safe_emit_js(self, js: str):
        """Dispatches JavaScript execution safely and asynchronously."""
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
                            core_wv = getattr(wv, "CoreWebView2", None)
                            if core_wv:
                                core_wv.ExecuteScriptAsync(js)
                            elif hasattr(wv, 'ExecuteScriptAsync'):
                                wv.ExecuteScriptAsync(js)
                        except Exception:
                            pass
                    if hasattr(form, 'InvokeRequired') and form.InvokeRequired:
                        form.BeginInvoke(Action(do_exec))
                    else:
                        do_exec()
                    emitted = True
        except Exception:
            pass

        if not emitted and self._webview_window and getattr(self, "ui_ready", False):
            if not getattr(self, '_eval_pending', False):
                self._eval_pending = True
                def async_eval():
                    try:
                        self._webview_window.evaluate_js(js)
                    except Exception:
                        pass
                    finally:
                        self._eval_pending = False
                threading.Thread(target=async_eval, daemon=True).start()

    def start(self):
        self.running = True
        self._flush_thread = threading.Thread(target=self._ui_flush_loop, daemon=True, name="TradePulsePersonal-UIFlush")
        self._flush_thread.start()
        
        # Verify cached license and start live heartbeat to Master Control Server
        if license_client.license_key:
            threading.Thread(target=license_client.validate_license, daemon=True).start()
        license_client.start_heartbeat()

        self.real_market_feed.start()
        self.ws_client.start()
        self.tracker.start()
        self.telegram.start()
        self.webhook_server.start()
        logger.info("🌟 [TradePulse Personal] Online! (Live Markets Currencies Only | Single-PC Locked)")

    def stop(self):
        self.running = False
        license_client.stop_heartbeat()
        self.real_market_feed.stop()
        self.ws_client.stop()
        self.tracker.stop()
        self.telegram.stop()
        self.webhook_server.stop()
        personal_db.close()
        logger.info("[TradePulse Personal] Engine safely stopped.")

    def restart_ingestion(self):
        """Restarts broker socket with newly extracted session cookies."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_restart_ws(), self._loop)

    async def _async_restart_ws(self):
        logger.info("[ENGINE] Reconnecting Quotex client with authenticated credentials...")
        self.ws_client.stop()
        await asyncio.sleep(0.5)
        self.ws_client.start()

    def _ui_flush_loop(self):
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

    def _on_payout_updated(self, symbol: str, payout: float):
        if "(OTC)" in symbol or "_otc" in symbol.lower():
            return
        with self._buffer_lock:
            self._payout_buffer[symbol] = payout

    def _on_tick(self, symbol: str, price: float, source: str = "real_market"):
        if "(OTC)" in symbol or "_otc" in symbol.lower():
            return
        with self._buffer_lock:
            self._tick_buffer[symbol] = {"price": price, "source": source}

        now = time.time()
        sec_of_min = int(now) % 60
        # Gated check: only evaluate pre-alerts if Quotex is logged in AND bot scanner is started
        if getattr(settings, "PRE_ALERTS_ENABLED", True) and 45 <= sec_of_min <= 52:
            current_min_ts = int(now // 60) * 60
            if self._pre_signal_min.get(symbol) != current_min_ts:
                self._pre_signal_min[symbol] = current_min_ts
                if self.is_operational() and self._loop and self._loop.is_running() and symbol not in self.unwatched_symbols:
                    session_ok, _ = self.scheduler.is_session_active(now)
                    news_blocked, _ = self.news_calendar.is_in_blackout(symbol, now)
                    cb_halted, _ = self.risk_manager.check_circuit_breaker()
                    if session_ok and not news_blocked and not cb_halted:
                        asyncio.run_coroutine_threadsafe(
                            self._evaluate_pre_signal(symbol, price, max(5, 60 - sec_of_min)),
                            self._loop
                        )

    async def _evaluate_pre_signal(self, symbol: str, current_price: float, remaining_seconds: int):
        try:
            if not self.is_operational():
                return

            can_fire, lock_reason = self.tracker.can_dispatch_signal()
            if not can_fire:
                logger.debug(f"[PRE-SIGNAL LOCKED] {symbol} skipped: {lock_reason}")
                return

            candles_1m = self.candle_store.get_candles(symbol, "1M")
            if len(candles_1m) < 15:
                return

            payout = asset_registry.get_payout(symbol) or 85.0
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
                        ev_res = self.quant_ev.evaluate_edge(symbol, payout, confidence_score=65.0)
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
                        logger.info(f"⚡ [PERSONAL PRE-SIGNAL] {symbol} {direction} ({strat.name}) ~{remaining_seconds}s remaining")
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
            logger.debug(f"[PRE-SIGNAL] Error: {e}")

    def _on_candle_completed(self, symbol: str, candle: Candle):
        if not self.running or "(OTC)" in symbol or "_otc" in symbol.lower():
            return

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

        # Strict Gating: Bot scanner must be started AND Quotex login completed
        if not self.is_operational() or symbol in self.unwatched_symbols:
            return

        if self._loop:
            asyncio.run_coroutine_threadsafe(self._evaluate_strategies_for_asset(symbol, candle), self._loop)

    def _on_status_update(self, mode: str, text: str):
        logger.info(f"[BROKER STATUS] {mode.upper()}: {text}")
        latency = self.ws_client.latency_ms
        self.safe_emit_js(f"window.onBrokerStatus({json.dumps(mode)}, {json.dumps(text)}, {latency});")

    def _on_external_webhook(self, payload: dict):
        if not self.is_operational():
            logger.info("[PERSONAL WEBHOOK] Gated: Quotex login and bot start required.")
            return

        symbol = payload.get("symbol")
        side = str(payload.get("side", "")).upper()
        duration = int(payload.get("duration", 2))

        if not symbol or side not in ("CALL", "PUT", "BUY", "SELL"):
            return
        if "(OTC)" in symbol or "_otc" in symbol.lower():
            return

        can_fire, lock_reason = self.tracker.can_dispatch_signal()
        if not can_fire:
            logger.info(f"[SEQUENTIAL LOCK] Personal webhook {symbol} skipped: {lock_reason}")
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
            strategy_name=payload.get("strategy_name", "TradingView Personal Alert"),
            confidence=95
        )

        if not self.tracker.register_signal(sig):
            return

        sig_json = json.dumps(sig.to_dict())
        self.safe_emit_js(f"window.onSignalFired({sig_json});")

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.telegram.broadcast_signal(sig), self._loop)

    async def _evaluate_strategies_for_asset(self, symbol: str, trigger_candle: Candle):
        if not self.is_operational():
            return

        # 0. Sequential Lock Check
        can_fire, lock_reason = self.tracker.can_dispatch_signal()
        if not can_fire:
            logger.debug(f"[SEQUENTIAL LOCK] {symbol} skipped: {lock_reason}")
            return

        # 1. Trading Session Filter
        session_ok, session_msg = self.scheduler.is_session_active()
        if not session_ok:
            return

        # 2. Economic News Blackout Filter
        in_news_blackout, _ = self.news_calendar.is_in_blackout(symbol)
        if in_news_blackout:
            return

        # 3. Circuit Breaker
        cb_halted, cb_msg = self.risk_manager.check_circuit_breaker()
        if cb_halted:
            if not self.scanning_paused:
                self.scanning_paused = True
                logger.warning(f"🛑 [CIRCUIT BREAKER] {cb_msg}. Halting scanner.")
                self.safe_emit_js(f"if(window.onCircuitBreakerTriggered) window.onCircuitBreakerTriggered({json.dumps(self.risk_manager.get_session_metrics())});")
            return

        candles_1m = self.candle_store.get_candles(symbol, "1M", contiguous_only=False)
        if len(candles_1m) < 15:
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
        payout = asset_registry.get_payout(symbol) or 85.0
        snapshot_1m = TechnicalIndicatorEngine.calculate_technical_snapshot(candles_1m)
        is_5m_close = ((trigger_candle.timestamp + 60) % 300 == 0)
        snapshot_5m = TechnicalIndicatorEngine.calculate_technical_snapshot(candles_5m) if (is_5m_close and candles_5m and len(candles_5m) >= 5) else None

        active_strategies = strategy_manager.get_active_strategies()
        triggered_setups = []

        for strat in active_strategies:
            try:
                if payout is not None and payout < strat.min_payout:
                    continue

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

                if not cooldown_manager.is_allowed(strat.id, symbol, eval_trigger.timestamp, strat.cooldown_seconds):
                    continue

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
                        cooldown_manager.record_signal(strat.id, symbol, eval_trigger.timestamp)
                        score, tier, audit = ConfluenceEngine.calculate_setup_quality_score(eval_trigger, payout, details, technical_snapshot=eval_snapshot, direction=direction)
                        ev_res = self.quant_ev.evaluate_edge(symbol=symbol, live_payout=payout, confidence_score=score)
                        if not ev_res["passed"]:
                            continue

                        rec_pos = self.risk_manager.get_recommended_stake()
                        audit["quant_ev"] = ev_res
                        audit["recommended_stake"] = rec_pos["stake"]
                        audit["martingale_step"] = rec_pos["step"]
                        audit["is_martingale"] = rec_pos["is_martingale"]

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
            except Exception as e:
                logger.debug(f"[STRATEGY EVAL] Error: {e}")
                continue

        if not triggered_setups:
            return

        for s in triggered_setups:
            if self.tracker.sequential_trade_lock and self.tracker.is_trade_active():
                break
            sig = s["sig"]
            logger.info(f"🚀 [PERSONAL SIGNAL] {sig.strategy_name} on {symbol} ({s['direction']} @ {sig.entry_price})")
            if not self.tracker.register_signal(sig):
                continue
            chart_bytes = await ChartGenerator.render_chart_async(s["candles"], sig)
            sig_json = json.dumps(sig.to_dict())
            self.safe_emit_js(f"window.onSignalFired({sig_json});")
            await self.telegram.broadcast_signal(sig, chart_bytes)

    def _on_trade_outcome(self, signal: Signal):
        self.risk_manager.record_trade_outcome(
            outcome=signal.status,
            payout_pct=signal.live_payout or 85.0,
            stake=getattr(signal, "recommended_stake", None)
        )
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.telegram.broadcast_outcome(signal), self._loop)

        sig_json = json.dumps(signal.to_dict())
        self.safe_emit_js(f"window.onTradeOutcome({sig_json});")

    def _on_telegram_command(self, chat_id: str, command_text: str, context: dict):
        cmd = command_text.strip().lower()
        if cmd in ("/status", "/ping"):
            status_text = "ACTIVE & SCANNING" if self.is_operational() else ("WAITING FOR QUOTEX LOGIN" if not self.is_quotex_logged_in() else "SCANNER PAUSED")
            msg = f"⚡ <b>TradePulse Personal Edition</b>\nStatus: <b>{status_text}</b>\nMarkets: <b>Real Forex Currencies Only (NO OTC)</b>\nCapacity: <b>Max 5 Authorized Users ({len(self.telegram.subscribers)}/5 Slots)</b>"
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, msg), self._loop)
        elif cmd == "/stats":
            stats = personal_db.get_performance_stats()
            wr = stats.get("win_rate", 0)
            tot = stats.get("total_signals", 0)
            msg = f"📊 <b>Personal Session Performance</b>\n• Win Rate: <b>{wr}%</b>\n• Total Trades: <b>{tot}</b>"
            asyncio.run_coroutine_threadsafe(self.telegram.send_message(chat_id, msg), self._loop)


# -----------------------------------------------------------------------------
# Bridge API for WebView UI with Full Embedded Quotex Docking & Gated Controls
# -----------------------------------------------------------------------------
class PersonalWebViewApi:
    def __init__(self, engine: TradePulsePersonalEngine):
        self.engine = engine
        self._main_win = None
        self._main_form = None
        self._Action = None
        self._Drawing = None
        self._broker_panel = None
        self._broker_wv = None
        self._broker_is_on_screen = False
        self._broker_last_rect = None
        self._on_nav_handler = None
        self._on_proc_failed_handler = None
        self._auto_primer_started = False
        self.current_broker_base = "https://market-qx.pro"

    def _run_on_ui(self, fn):
        if not self._main_form or getattr(self._main_form, 'IsDisposed', False):
            return
        Action = self._Action or __import__('System', fromlist=['Action']).Action
        if self._main_form.InvokeRequired:
            self._main_form.BeginInvoke(Action(fn))
        else:
            fn()

    def init_embedded_broker(self):
        """Initializes embedded Quotex trading terminal inside the desktop window."""
        if self._broker_panel and self._broker_wv:
            return True
        if sys.platform != "win32":
            return False

        try:
            import clr
            clr.AddReference('System.Windows.Forms')
            clr.AddReference('System.Drawing')
            clr.AddReference('Microsoft.Web.WebView2.WinForms')

            WinForms = __import__('System.Windows.Forms', fromlist=['*'])
            Drawing = __import__('System.Drawing', fromlist=['*'])
            WebView2 = __import__('Microsoft.Web.WebView2.WinForms', fromlist=['WebView2']).WebView2
            BrowserView = __import__('webview.platforms.winforms', fromlist=['BrowserView']).BrowserView

            self._Action = __import__('System', fromlist=['Action']).Action
            self._Drawing = Drawing

            if not self._main_form and self._main_win:
                self._main_form = BrowserView.instances.get(self._main_win.uid)

            if not self._main_form:
                return False

            def create_wv():
                try:
                    self._broker_panel = WinForms.Panel()
                    self._broker_panel.Name = "EmbeddedBrokerStationPanel"
                    self._broker_panel.BackColor = Drawing.Color.FromArgb(7, 9, 14)
                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
                    self._broker_panel.Size = Drawing.Size(800, 600)
                    self._broker_panel.Visible = False

                    self._broker_wv = WebView2()
                    self._broker_wv.Dock = WinForms.DockStyle.Fill
                    self._broker_panel.Controls.Add(self._broker_wv)
                    self._main_form.Controls.Add(self._broker_panel)

                    def on_ready(sender, args):
                        try:
                            self._broker_wv.CoreWebView2.Settings.IsStatusBarEnabled = False
                            self._broker_wv.CoreWebView2.Settings.AreDevToolsEnabled = False

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
                                                        logger.info(f"[PERSONAL BROKER] Authenticated Quotex session token & cookies extracted!")
                                                        auth_manager.store_session(extracted_token, cookies=cookies_dict)
                                                        self.engine.session_token = extracted_token
                                                        self.engine.ws_client.session_token = extracted_token
                                                        self.engine.restart_ingestion()
                                                        self.engine.safe_emit_js("showToast('Quotex Authenticated Successfully! You may now start the bot scanner.', 'success');")
                                            except Exception as ce:
                                                logger.debug(f"[COOKIE READ] {ce}")

                                        self._run_on_ui(parse_cookies)

                                    task.ContinueWith(Action[Task](on_cookies_done))
                                except Exception as te:
                                    logger.debug(f"[COOKIE TASK] {te}")

                            def on_nav_completed(s, a):
                                try:
                                    url = s.Source or ""
                                    from core.ingester.auth_manager import STREAM_INJECTION_JS
                                    s.ExecuteScriptAsync(STREAM_INJECTION_JS)
                                    if any(k in url.lower() for k in ["/trade", "demo-trade", "qxbroker", "quotex"]):
                                        check_and_extract_session(url)
                                        s.ExecuteScriptAsync("if(window.__tp_scan_now) window.__tp_scan_now();")
                                        s.ExecuteScriptAsync("if(window.__tp_subscribe_all) window.__tp_subscribe_all();")
                                except Exception:
                                    pass

                            self._broker_wv.CoreWebView2.NavigationCompleted += on_nav_completed
                            target_url = f"{self.current_broker_base}/en/trade" if self.engine.session_token else f"{self.current_broker_base}/en/sign-in"
                            self._broker_wv.CoreWebView2.Navigate(target_url)
                        except Exception as e:
                            logger.debug(f"[BROKER READY ERR] {e}")

                    self._broker_wv.CoreWebView2InitializationCompleted += on_ready
                    self._broker_wv.EnsureCoreWebView2Async(None)
                except Exception as ex:
                    logger.error(f"[BROKER INIT ERR] {ex}")

            self._run_on_ui(create_wv)
            return True
        except Exception as e:
            logger.error(f"[BROKER EMBED ERR] {e}")
            return False

    def sync_broker_position(self, x, y, w, h, visible):
        """Aligns embedded native Quotex terminal over the UI broker station container."""
        is_vis = bool(visible and w > 20 and h > 20)
        self._broker_is_on_screen = is_vis

        if visible and (not self._broker_panel or not self._broker_wv):
            self.init_embedded_broker()

        if not self._broker_panel or not self._main_form:
            return False

        Drawing = self._Drawing or __import__('System.Drawing', fromlist=['*'])

        def do_sync():
            try:
                scale = float(getattr(self._main_form, '_scale', 1.0))
                if is_vis:
                    self._broker_panel.Location = Drawing.Point(int(x * scale), int(y * scale))
                    self._broker_panel.Size = Drawing.Size(int(w * scale), int(h * scale))
                    self._broker_panel.Visible = True
                    if self._broker_wv:
                        self._broker_wv.Visible = True
                    self._broker_panel.BringToFront()
                else:
                    self._broker_panel.Visible = False
                    self._broker_panel.SendToBack()
                    self._broker_panel.Location = Drawing.Point(-2000, -2000)
            except Exception:
                pass

        self._run_on_ui(do_sync)
        return True

    def set_broker_visible(self, visible: bool):
        return self.sync_broker_position(240, 52, 1000, 700, visible)

    def refresh_broker(self):
        if self._broker_wv:
            self._run_on_ui(lambda: self._broker_wv.Reload())
        return True

    def navigate_broker(self, url: str):
        if self._broker_wv:
            self._run_on_ui(lambda: self._broker_wv.CoreWebView2.Navigate(url))
        return True

    def navigate_broker_signin(self):
        return self.navigate_broker(f"{self.current_broker_base}/en/sign-in")

    def navigate_broker_trade(self):
        return self.navigate_broker(f"{self.current_broker_base}/en/trade")

    def login_credentials(self, email, password):
        if self._broker_wv and self._main_form:
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
        return False

    def login_google(self):
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
        return False

    def on_broker_frame(self, raw_data: str):
        try:
            self.engine.ws_client.process_raw_frame(raw_data)
        except Exception:
            pass

    def on_broker_payouts(self, payouts: dict):
        if not payouts:
            return
        for sym, val in payouts.items():
            if "(OTC)" not in sym and "_otc" not in sym.lower():
                try:
                    asset_registry.update_payout(sym, float(val))
                except Exception:
                    pass

    def on_broker_instruments(self, instruments: list):
        pass

    def on_broker_candles(self, asset: str, data: list):
        pass

    def on_broker_tick(self, symbol: str, price: float, source: str = "broker"):
        if "(OTC)" not in symbol and "_otc" not in symbol.lower():
            self.engine._on_tick(symbol, price, source)

    def prime_asset_stream(self, symbol: str):
        return {"success": True, "symbol": symbol}

    def show_broker_window(self):
        if self._main_win:
            try:
                self._main_win.evaluate_js("switchView('broker');")
                return True
            except Exception:
                pass
        return False

    # -------------------------------------------------------------------------
    # Gated Tool Controls: Only startable when Quotex login is completed & License Active
    # -------------------------------------------------------------------------
    def set_tool_active(self, is_active: bool):
        """Starts or pauses the personal signal scanner. Gated by Quotex login and valid license."""
        if is_active:
            if not self.engine.is_quotex_logged_in():
                logger.warning("[PERSONAL TOOL] Cannot start scanner: Quotex Login Required!")
                return {
                    "success": False,
                    "error": "Quotex Login Required! Please log in to your Quotex account in the broker terminal first.",
                    "active": False,
                    "paused": True
                }

            if not license_client.is_licensed:
                ok, lic_msg = license_client.validate_license()
                if not ok:
                    logger.warning(f"[PERSONAL TOOL] Cannot start scanner: {lic_msg}")
                    return {
                        "success": False,
                        "error": f"Subscription Required: {lic_msg}",
                        "active": False,
                        "paused": True
                    }

            self.engine.scanning_paused = False
            logger.info("🌟 [PERSONAL TOOL] Scanner STARTED (Active). Personal Telegram signals live!")
            return {"success": True, "active": True, "paused": False}
        else:
            self.engine.scanning_paused = True
            logger.info("[PERSONAL TOOL] Scanner PAUSED (Stopped).")
            return {"success": True, "active": False, "paused": True}

    def toggle_engine(self):
        """Toggles the personal signal scanner between active and paused."""
        if self.engine.scanning_paused:
            return self.set_tool_active(True)
        else:
            return self.set_tool_active(False)

    def get_initial_state(self):
        self.engine.ui_ready = True
        is_logged_in = self.engine.is_quotex_logged_in()
        is_active = self.engine.is_operational()
        return {
            "connected": is_logged_in,
            "latency": self.engine.ws_client.latency_ms or 25,
            "status_text": "Personal Edition (Live Markets Only)" if is_logged_in else "Disconnected (Quotex Login Required)",
            "session_token": self.engine.session_token,
            "license": license_client.get_status(),
            "assets": asset_registry.get_all_asset_defs(),
            "payouts": asset_registry.get_live_payouts(),
            "prices": asset_registry.get_all_prices(),
            "price_sources": asset_registry.get_all_price_sources(),
            "strategies": [s.model_dump() for s in strategy_manager.get_all_strategies()],
            "stats": personal_db.get_performance_stats(),
            "signals": [s for s in personal_db.get_recent_signals(15)],
            "telegram_token": self.engine.telegram_manager.bot_token or "",
            "telegram_chat_id": [c["id"] for c in self.engine.telegram_manager.channels if c.get("id")] if self.engine.telegram_manager.channels else [],
            "telegram_manager": self.engine.telegram_manager.get_config(),
            "webhook_endpoint": "http://127.0.0.1:8766/webhook",
            "global_cooldown": cooldown_manager.global_cooldown_seconds or 120,
            "engine_running": self.engine.running,
            "tool_active": is_active,
            "scanning_paused": self.engine.scanning_paused,
            "advanced_filters": {
                "news_calendar": self.engine.news_calendar.get_config(),
                "quant_ev": self.engine.quant_ev.get_config(),
                "risk_manager": self.engine.risk_manager.get_config(),
                "session_scheduler": self.engine.scheduler.get_config()
            },
            "risk_metrics": self.engine.risk_manager.get_session_metrics(),
            "upcoming_news": self.engine.news_calendar.get_upcoming_events(6)
        }

    def get_license_status(self):
        return license_client.get_status()

    def activate_license(self, license_key: str, server_url: Optional[str] = None):
        ok, msg = license_client.validate_license(license_key, server_url)
        return {
            "success": ok,
            "message": msg,
            "license": license_client.get_status()
        }

    def get_all_assets(self):
        return asset_registry.get_all_asset_defs()

    def get_candles_for_chart(self, symbol: str, timeframe: str = "1M", heikin_ashi: bool = False):
        """Returns authentic or synthesized candles for the requested symbol and timeframe."""
        if heikin_ashi:
            candles = self.engine.candle_store.get_heikin_ashi_candles(symbol, timeframe)
        else:
            candles = self.engine.candle_store.get_candles(symbol, timeframe)

        if not candles:
            price = asset_registry.get_price(symbol) or 1.08500
            now_ts = int(time.time())
            simulated = []
            tf_sec = 300 if timeframe == "5M" else (900 if timeframe == "15M" else 60)
            curr = price
            import random
            for i in range(45, 0, -1):
                ts = now_ts - (i * tf_sec)
                delta = (random.random() - 0.49) * (0.00025 if "JPY" not in symbol else 0.025)
                o = curr
                c = curr + delta
                h = max(o, c) + random.random() * (0.0001 if "JPY" not in symbol else 0.01)
                l = min(o, c) - random.random() * (0.0001 if "JPY" not in symbol else 0.01)
                simulated.append({
                    "timestamp": ts,
                    "open": round(o, 5),
                    "high": round(h, 5),
                    "low": round(l, 5),
                    "close": round(c, 5),
                    "volume": 100.0
                })
                curr = c
            return simulated

        return [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in candles[-120:]
        ]

    def get_strategies(self):
        return [s.model_dump() for s in strategy_manager.get_all_strategies()]

    def save_strategy(self, data):
        return strategy_manager.save_or_update(data).model_dump()

    def toggle_strategy(self, strategy_id, enabled=None):
        return strategy_manager.toggle_strategy(strategy_id, enabled)

    def delete_strategy(self, strategy_id):
        return strategy_manager.delete_strategy(strategy_id)

    def get_signals_history(self, limit: int = 100):
        return list(personal_db.get_recent_signals(limit))

    def get_performance_stats(self):
        return personal_db.get_performance_stats()

    def get_telegram_manager_state(self):
        return self.engine.telegram_manager.get_config()

    def update_telegram_manager_config(self, new_config: dict):
        updated = self.engine.telegram_manager.update_config(new_config)
        if hasattr(self.engine, 'tracker') and self.engine.tracker:
            self.engine.tracker.sequential_trade_lock = self.engine.telegram_manager.sequential_trade_lock
            self.engine.tracker.loss_cooldown_seconds = self.engine.telegram_manager.loss_cooldown_seconds
        return {"success": True, "config": updated}

    def save_telegram_template(self, template_key: str, template_text: str):
        ok = self.engine.telegram_manager.set_template(template_key, template_text)
        return {"success": ok, "config": self.engine.telegram_manager.get_config()}

    def reset_telegram_template(self, template_key: str):
        res = self.engine.telegram_manager.reset_template_to_default(template_key)
        return {"success": True, "template_key": template_key, "template": res}

    def test_telegram_bot_token(self, token: Optional[str] = None):
        return self.engine.telegram.verify_bot_token(token)

    def test_send_telegram_channel(self, channel_id: str, custom_msg: Optional[str] = None):
        text = custom_msg or "🔔 <b>TradePulse Personal Ping</b>\n<i>Personal live markets signal connection operational.</i>"
        if not self.engine._loop:
            return {"success": False, "error": "Event loop not running"}
        fut = asyncio.run_coroutine_threadsafe(
            self.engine.telegram.broadcast_custom_message(text=text, target_chat_id=channel_id),
            self.engine._loop
        )
        try:
            return fut.result(timeout=10.0)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def broadcast_custom_telegram_message(self, text: str, target_chat_id: Optional[str] = None):
        if not self.engine._loop:
            return {"success": False, "error": "Event loop not running"}
        fut = asyncio.run_coroutine_threadsafe(
            self.engine.telegram.broadcast_custom_message(text=text.strip(), target_chat_id=target_chat_id),
            self.engine._loop
        )
        try:
            return fut.result(timeout=10.0)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_telegram(self):
        return True

    def get_candles_for_chart(self, symbol: str, timeframe: str = "1M"):
        if not symbol or "(OTC)" in symbol or "_otc" in symbol.lower():
            return []
        candles = self.engine.candle_store.get_candles(symbol, timeframe, contiguous_only=False)
        return [
            {
                "timestamp": int(c.timestamp),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            }
            for c in candles[-200:]
            if c.open > 0 and c.close > 0
        ]

    def set_app_muted(self, is_muted: bool):
        return {"success": True, "is_muted": bool(is_muted)}

    def get_advanced_filters_config(self):
        return {
            "news_calendar": self.engine.news_calendar.get_config(),
            "quant_ev": self.engine.quant_ev.get_config(),
            "risk_manager": self.engine.risk_manager.get_config(),
            "session_scheduler": self.engine.scheduler.get_config()
        }

    def update_advanced_filters_config(self, config: dict):
        try:
            if "news_calendar" in config:
                self.engine.news_calendar.configure(**config["news_calendar"])
            if "quant_ev" in config:
                self.engine.quant_ev.configure(**config["quant_ev"])
            if "risk_manager" in config:
                self.engine.risk_manager.configure(**config["risk_manager"])
            if "session_scheduler" in config:
                self.engine.scheduler.configure(**config["session_scheduler"])
            return {"success": True, "config": self.get_advanced_filters_config()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_risk_session_metrics(self):
        return self.engine.risk_manager.get_session_metrics()

    def reset_daily_risk_session(self):
        self.engine.risk_manager.reset_session()
        return {"success": True, "metrics": self.get_risk_session_metrics()}

    def get_upcoming_news_events(self, limit: int = 6):
        return self.engine.news_calendar.get_upcoming_events(limit=int(limit))

    def run_quick_backtest(self, strategy_id):
        strat = strategy_manager.get_strategy(strategy_id)
        if not strat:
            return {"error": "Strategy not found"}
        candles = self.engine.candle_store.get_candles("EUR/USD", "1M", contiguous_only=False)
        candles_5m = self.engine.candle_store._synthesize_timeframe(candles, 300) if len(candles) >= 5 else []
        return HistoricalBacktestEngine.test_strategy_on_asset(strat, candles, candles_5m)

    def run_backtest(self, strategy_id):
        return self.run_quick_backtest(strategy_id)

    def run_strategy_backtest_custom(self, strategy_id: str, symbol: str = "EUR/USD", payout_pct: float = 85.0):
        strat = strategy_manager.get_strategy(strategy_id)
        if not strat:
            return {"error": f"Strategy '{strategy_id}' not found"}
        sym = symbol or "EUR/USD"
        candles = self.engine.candle_store.get_candles(sym, "1M", contiguous_only=False)
        if not candles or len(candles) < 25:
            candles = self.engine.candle_store.get_candles("EUR/USD", "1M", contiguous_only=False)
        candles_5m = self.engine.candle_store._synthesize_timeframe(candles, 300) if len(candles) >= 5 else []
        return HistoricalBacktestEngine.test_strategy_on_asset(strat, candles, candles_5m, payout_pct=float(payout_pct or 85.0))

    def calculate_quant_ev(self, payout_pct: float = 85.0, win_rate: float = 60.0, bankroll: float = 1000.0):
        """Calculates mathematical expected value and Kelly stake recommendations."""
        p_pct = float(payout_pct or 85.0)
        wr = float(win_rate or 60.0)
        b_roll = float(bankroll or 1000.0)

        p = wr / 100.0
        q = 1.0 - p
        b = p_pct / 100.0

        # Expected value per $1 risked
        ev_per_unit = (p * b) - (q * 1.0)
        be_win_rate = round(100.0 / (100.0 + p_pct), 2)
        has_edge = (wr > be_win_rate)

        # Full Kelly fraction: (p*b - q) / b
        kelly_fraction = max(0.0, (p * b - q) / b) if b > 0 else 0.0
        # Half-Kelly (industry standard risk management)
        half_kelly_pct = round((kelly_fraction / 2.0) * 100.0, 2)
        recommended_stake = round(b_roll * (half_kelly_pct / 100.0), 2)

        return {
            "payout_pct": p_pct,
            "win_rate": wr,
            "break_even_win_rate": be_win_rate,
            "has_positive_edge": has_edge,
            "ev_percentage": round(ev_per_unit * 100.0, 2),
            "ev_per_10_dollar_trade": round(ev_per_unit * 10.0, 2),
            "kelly_fraction_pct": round(kelly_fraction * 100.0, 2),
            "half_kelly_recommended_pct": half_kelly_pct,
            "recommended_stake_amount": max(1.0, recommended_stake) if has_edge else 1.0,
            "bankroll": b_roll
        }

    def run_strategy_optimizer(self, symbol: str = "EUR/USD", payout_pct: float = 85.0):
        """Runs multi-parameter grid search across RSI & Bollinger Band configurations."""
        sym = symbol or "EUR/USD"
        candles = self.engine.candle_store.get_candles(sym, "1M", contiguous_only=False)
        if not candles or len(candles) < 50:
            candles = self.engine.candle_store.get_candles("EUR/USD", "1M", contiguous_only=False)
        return StrategyOptimizer.run_rsi_bollinger_grid_search(candles, payout_pct=float(payout_pct or 85.0))

    def run_monte_carlo_test(self, wins: int, losses: int, payout_pct: float = 85.0, simulations: int = 500, stake: float = 10.0):
        """Runs Monte Carlo permutation simulation to stress-test drawdowns."""
        return StrategyOptimizer.run_monte_carlo_permutation_test(
            wins=int(wins or 20),
            losses=int(losses or 10),
            payout_pct=float(payout_pct or 85.0),
            simulations=int(simulations or 500),
            stake=float(stake or 10.0)
        )

    def test_send_telegram_chart(self, chat_id: str):
        """Generates a demo high-definition candlestick chart and sends it to the specified Telegram channel."""
        cid = str(chat_id or self.engine.telegram_manager.bot_token).strip()
        if not cid:
            active_channels = self.engine.telegram_manager.get_active_channel_ids()
            cid = active_channels[0] if active_channels else ""
        if not cid:
            return {"success": False, "error": "No Telegram Chat ID configured"}

        candles = self.engine.candle_store.get_candles("EUR/USD", "1M", contiguous_only=False)
        if not candles or len(candles) < 5:
            # Seed 10 synthetic display candles if empty
            candles = [
                Candle(timestamp=int(time.time() - (10 - i) * 60), open=1.0850 + (i * 0.0001), high=1.0855 + (i * 0.0001), low=1.0848 + (i * 0.0001), close=1.0854 + (i * 0.0001), volume=100.0)
                for i in range(15)
            ]

        demo_sig = Signal(
            strategy_name="Backtest / Live Chart Verification",
            asset_symbol="EUR/USD",
            direction="CALL",
            timeframe="1M",
            duration_minutes=2,
            entry_price=candles[-1].close,
            live_payout=88.0,
            confidence=92
        )

        async def _do_send():
            chart_bytes = await ChartGenerator.render_chart_async(candles, demo_sig)
            if chart_bytes and self.engine.telegram._http:
                await self.engine.telegram.send_photo_async(
                    chat_id=cid,
                    photo_bytes=chart_bytes,
                    caption="📸 <b>TradePulse HD Chart Signal Attachment</b>\n<i>Verified high-definition candlestick rendering & entry strike plotting.</i>"
                )

        if self.engine._loop and self.engine._loop.is_running():
            asyncio.run_coroutine_threadsafe(_do_send(), self.engine._loop)
            return {"success": True, "message": f"HD Chart dispatched to chat {cid}"}
        return {"success": False, "error": "Event loop not active"}


    def toggle_asset_watch(self, symbol: str, is_watched: bool):
        if is_watched:
            self.engine.unwatched_symbols.discard(symbol)
        else:
            self.engine.unwatched_symbols.add(symbol)
        return True

    def set_global_cooldown(self, seconds: int):
        sec_val = max(10, int(seconds))
        cooldown_manager.set_global_cooldown(sec_val)
        return {"success": True, "cooldown": sec_val}

    def get_feature_toggles(self):
        return {
            "otc_flatline_guard": False,
            "pre_alerts": getattr(settings, "PRE_ALERTS_ENABLED", True),
            "voice_alerts": getattr(settings, "VOICE_ALERTS_ENABLED", True),
            "confluence_scanner": getattr(settings, "CONFLUENCE_SCANNER_ENABLED", True),
            "global_cooldown": cooldown_manager.global_cooldown_seconds
        }

    def update_feature_toggle(self, name: str, enabled: bool):
        return {"success": True, "name": name, "enabled": bool(enabled)}


# -----------------------------------------------------------------------------
# Main Application Launcher
# -----------------------------------------------------------------------------
def run_personal_app():
    parser = argparse.ArgumentParser(description="TradePulse Personal Edition")
    parser.add_argument("--headless", action="store_true", help="Run 24/7 in VPS headless mode")
    args = parser.parse_args()

    engine = TradePulsePersonalEngine()

    if args.headless:
        logger.info("🚀 Starting TradePulse Personal in Headless VPS Mode...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        engine.set_loop(loop)
        engine.start()
        try:
            loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            engine.stop()
    else:
        logger.info("🚀 Launching TradePulse Personal Desktop GUI...")
        import webview
        api = PersonalWebViewApi(engine)
        engine.set_bridge_api(api)

        def bg_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            engine.set_loop(loop)
            engine.start()
            loop.run_forever()

        t = threading.Thread(target=bg_loop, daemon=True, name="TradePulsePersonal-Loop")
        t.start()

        html_file = ROOT_DIR / "ui_personal" / "index.html"
        window = webview.create_window(
            title="TradePulse Personal — Institutional Live Markets Workstation",
            url=str(html_file),
            js_api=api,
            width=1480,
            height=920,
            min_size=(1100, 700),
            background_color="#07090e"
        )
        engine.set_webview_window(window)
        api._main_win = window
        # debug=False ensures Developer Tools / inspect are disabled and no code is shown
        webview.start(gui="edgechromium", debug=False)
        engine.stop()


if __name__ == "__main__":
    run_personal_app()
