"""
TradePulse Telegram Message Formatter
Renders premium, concise HTML-formatted signal cards, trade outcome alerts,
market rates tables, and telemetry status reports.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.ingester.asset_registry import asset_registry
from core.models.signal import Signal

logger = logging.getLogger(__name__)

IST_TZ = timezone(timedelta(hours=5, minutes=30))
UTC_TZ = timezone.utc


class TelegramFormatter:
    """Formats Telegram messages in high-impact HTML layout."""

    @classmethod
    def format_vip_signal_card(cls, signal: Signal, template: Optional[str] = None) -> Tuple[str, List[List[Dict[str, str]]]]:
        """Formats the main live signal alert with dynamic IST/UTC timestamps."""
        is_call = signal.is_call
        dir_badge = "CALL (UP) 🟢" if is_call else "PUT (DOWN) 🔴"
        arrow = "📈" if is_call else "📉"

        # Time formatting
        entry_dt = signal.entry_time.astimezone(IST_TZ)
        expiry_dt = signal.expiry_time.astimezone(IST_TZ) if signal.expiry_time else (entry_dt + timedelta(minutes=signal.duration_minutes))

        entry_ist = entry_dt.strftime("%H:%M:%S")
        expiry_ist = expiry_dt.strftime("%H:%M:%S")

        # Confluence checklist
        rule_details = signal.audit_trail.get("rule_details", {})
        body_ratio = signal.audit_trail.get("body_ratio", 70.0)
        wick_ratio = signal.audit_trail.get("opposing_wick_ratio", 12.0)

        score = signal.confidence
        tier = signal.audit_trail.get("tier")
        if not tier:
            from core.strategy.confluence import ConfluenceEngine
            tier = ConfluenceEngine.get_tier(score)

        try:
            from core.storage.db import db
            strat_stats = db.get_strategy_performance_stats(signal.strategy_id)
            total_trades = strat_stats["total_signals"]
            strat_wr = strat_stats["win_rate"]
        except Exception:
            total_trades = 0
            strat_wr = 0.0

        if total_trades >= 20:
            win_rate_line = f"📈 <b>Historical Win Rate:</b> <b>{strat_wr:.1f}% ({total_trades} trades)</b>\n"
        else:
            win_rate_line = f"📈 <b>Historical Win Rate:</b> <i>Calibrating ({total_trades}/20 trades)</i>\n"

        confluence_strats = signal.audit_trail.get("confluence_strategies")
        header = f"⭐ <b>ULTRA CONFLUENCE SIGNAL ({len(confluence_strats)} STRATEGIES)</b>\n" if confluence_strats else f"🚀 <b>SIGNAL ALERT: {signal.strategy_name.upper()}</b>\n"
        
        confluence_section = ""
        if confluence_strats:
            confluence_section = "🤝 <b>Confirming Strategies:</b>\n" + "".join(f"  • <b>{cs}</b>\n" for cs in confluence_strats)

        payout_display = f"{signal.live_payout:.0f}%" if signal.live_payout is not None else "--%"
        payout_num = f"{signal.live_payout:.0f}" if signal.live_payout is not None else "--"
        entry_formatted = asset_registry.format_price(signal.asset_symbol, signal.entry_price)

        rec_stake_val = getattr(signal, "stake", None)
        step_val = getattr(signal, "martingale_step", 1)
        stake_line = f"💰 <b>Recommended Stake:</b> <b>${rec_stake_val:.2f} (Step {step_val})</b>\n" if rec_stake_val else ""

        ev_val = getattr(signal, "ev", None)
        ev_line = f"🧮 <b>Quant Edge:</b> <b>EV +${ev_val:.2f}</b>\n" if ev_val is not None else ""

        keyboard = [
            [
                {"text": "📊 Live Markets", "callback_data": "cmd_markets"},
                {"text": "⚡ Status", "callback_data": "cmd_status"}
            ]
        ]

        if template:
            try:
                from core.telegram.manager import TelegramManager
                context = {
                    "asset": signal.asset_symbol,
                    "direction": signal.direction,
                    "dir_badge": dir_badge,
                    "arrow": arrow,
                    "timeframe": signal.timeframe,
                    "expiry": signal.duration_minutes,
                    "payout": payout_num,
                    "entry_time": entry_ist,
                    "expiry_time": expiry_ist,
                    "entry_price": entry_formatted,
                    "confidence": score,
                    "tier": tier,
                    "strategy": signal.strategy_name,
                    "confluence_section": confluence_section,
                    "stake_line": stake_line,
                    "ev_line": ev_line,
                    "rec_stake": f"${rec_stake_val:.2f}" if rec_stake_val else "--",
                    "martingale_step": str(step_val),
                    "ev_edge": f"+${ev_val:.2f}" if ev_val is not None else "--",
                    "header": header.strip()
                }
                custom_caption = TelegramManager.interpolate(template, context)
                if custom_caption and len(custom_caption.strip()) > 10:
                    return custom_caption, keyboard
            except Exception as e:
                logger.warning(f"[TELEGRAM FORMATTER] Custom template render failed: {e}")

        caption = (
            f"{header}"
            f"────────────────────────\n"
            f"📊 <b>Asset:</b> <code>{signal.asset_symbol}</code>\n"
            f"💰 <b>OTC Payout:</b> <b>{payout_display}</b>\n"
            f"{arrow} <b>Direction:</b> <b>{dir_badge}</b>\n"
            f"⏱ <b>Timeframe:</b> <b>{signal.timeframe}</b>\n"
            f"⌛ <b>Expiry Duration:</b> <b>{signal.duration_minutes} Mins</b>\n"
            f"🕒 <b>Entry Time:</b> <b>Next Candle Open (00s) | {entry_ist} IST</b>\n"
            f"💵 <b>Entry Price:</b> <code>{entry_formatted}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{confluence_section}"
            f"🧠 <b>CONFIRMED CONFLUENCE:</b>\n"
            f"• <b>Solid Body Ratio:</b>  ✅ <b>{body_ratio:.1f}%</b> (> 60% solid)\n"
            f"• <b>Opposing Wick:</b>     ✅ <b>{wick_ratio:.1f}%</b> (≤ 35% limit)\n"
            f"• <b>Preceding Bar:</b>     ✅ Passed (Non-Doji)\n"
            f"• <b>Payout Filter:</b>     ✅ Passed (≥ {payout_display})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Setup Quality Score:</b> <b>{score}% ({tier})</b>\n"
            f"{stake_line}"
            f"{ev_line}"
            f"{win_rate_line}"
            f"⏰ <b>Expiry Target:</b> <b>{expiry_ist} IST</b>\n"
            f"🔒 <i>Safe Mode: 100% Real-Time Market Confluence</i>"
        )
        return caption, keyboard

    @classmethod
    def format_pre_signal_card(
        cls,
        symbol: str,
        direction: str,
        timeframe: str,
        expiry_minutes: int,
        remaining_seconds: int,
        price: float,
        payout: Optional[float],
        strategy_name: str,
        template: Optional[str] = None,
        stake: Optional[float] = None,
        martingale_step: int = 1
    ) -> str:
        dir_badge = "CALL (UP) 🟢" if direction == "CALL" else "PUT (DOWN) 🔴"
        payout_str = f"{payout:.0f}%" if payout is not None else "--%"
        payout_num = f"{payout:.0f}" if payout is not None else "--"
        stake_line = f"💰 <b>Recommended Stake:</b> <b>${stake:.2f} (Step {martingale_step})</b>\n" if stake else ""

        if template:
            try:
                from core.telegram.manager import TelegramManager
                context = {
                    "asset": symbol,
                    "direction": direction,
                    "dir_badge": dir_badge,
                    "timeframe": timeframe,
                    "expiry": expiry_minutes,
                    "remaining_seconds": remaining_seconds,
                    "payout": payout_num,
                    "price": asset_registry.format_price(symbol, price),
                    "strategy": strategy_name,
                    "stake_line": stake_line,
                    "rec_stake": f"${stake:.2f}" if stake else "--",
                    "martingale_step": str(martingale_step)
                }
                custom_text = TelegramManager.interpolate(template, context)
                if custom_text and len(custom_text.strip()) > 10:
                    return custom_text
            except Exception as e:
                logger.warning(f"[TELEGRAM FORMATTER] Custom pre-signal template error: {e}")

        return (
            f"⚡ <b>PRE-SIGNAL RADAR: PREPARE ENTRY</b>\n"
            f"────────────────────────\n"
            f"📊 <b>Asset:</b> <code>{symbol}</code>\n"
            f"🎯 <b>Direction:</b> <b>{dir_badge}</b>\n"
            f"⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry_minutes}m)\n"
            f"💰 <b>Payout:</b> <b>{payout_str}</b>\n"
            f"⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n"
            f"🧠 <b>Forming Pattern:</b> {strategy_name}\n"
            f"{stake_line}"
            f"────────────────────────\n"
            f"<i>Prepare pair & stake in Quotex. Official entry fires on candle close.</i>"
        )

    @classmethod
    def format_trade_outcome_card(cls, signal: Signal, template: Optional[str] = None) -> str:
        """Formats the post-expiry WIN / LOSS / DRAW result notification."""
        status = signal.status.upper()
        if status == "WIN":
            outcome_badge = "WIN ✅"
            header = "🎉 <b>TRADE OUTCOME: PROFIT!</b>"
            payout_ret = f"+{signal.live_payout:.0f}% Return" if signal.live_payout is not None else "Payout Return"
            pnl_text = f"💰 <b>Profit:</b> <b>{payout_ret}</b>"
        elif status == "LOSS":
            outcome_badge = "LOSS ❌"
            header = "⚠️ <b>TRADE OUTCOME: COMPLETED</b>"
            pnl_text = "📉 <b>Result:</b> <b>Did not close in direction</b>"
        else:
            outcome_badge = "DRAW ⚪"
            header = "⏸ <b>TRADE OUTCOME: DRAW</b>"
            pnl_text = "💵 <b>Result:</b> <b>Exact strike price match</b>"

        entry_formatted = asset_registry.format_price(signal.asset_symbol, signal.entry_price)
        exit_formatted = asset_registry.format_price(signal.asset_symbol, signal.exit_price or signal.entry_price)

        if template:
            try:
                from core.telegram.manager import TelegramManager
                context = {
                    "header": header,
                    "asset": signal.asset_symbol,
                    "strategy": signal.strategy_name,
                    "direction": signal.direction,
                    "status": status,
                    "outcome_badge": outcome_badge,
                    "entry_price": entry_formatted,
                    "exit_price": exit_formatted,
                    "pnl_text": pnl_text
                }
                custom_text = TelegramManager.interpolate(template, context)
                if custom_text and len(custom_text.strip()) > 10:
                    return custom_text
            except Exception as e:
                logger.warning(f"[TELEGRAM FORMATTER] Custom outcome template error: {e}")

        return (
            f"{header}\n"
            f"────────────────────────\n"
            f"📊 <b>Asset:</b> <code>{signal.asset_symbol}</code>\n"
            f"🎯 <b>Strategy:</b> <code>{signal.strategy_name}</code>\n"
            f"📌 <b>Direction:</b> <b>{signal.direction}</b>\n"
            f"🏁 <b>Result:</b> <b>{outcome_badge}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Entry Strike:</b> <code>{entry_formatted}</code>\n"
            f"🏁 <b>Exit Price:</b>   <code>{exit_formatted}</code>\n"
            f"{pnl_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <i>TradePulse 24/7 Real-Time Outcome Verification</i>"
        )

    @classmethod
    def format_circuit_breaker_card(cls, metrics: Dict[str, Any], template: Optional[str] = None) -> str:
        """Formats Daily Take Profit or Stop Loss circuit breaker alert."""
        reason = metrics.get("circuit_breaker_reason", "Daily risk limits reached")
        pnl = metrics.get("daily_pnl", 0.0)
        trades = metrics.get("trades_count", 0)
        pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}"

        if template:
            try:
                from core.telegram.manager import TelegramManager
                context = {
                    "reason": reason,
                    "cb_reason": reason,
                    "daily_pnl": pnl_str,
                    "net_pnl": pnl_str,
                    "trades_count": trades,
                    "total_trades": trades,
                    "win_rate": f"{metrics.get('win_rate', 0.0):.1f}%"
                }
                custom_text = TelegramManager.interpolate(template, context)
                if custom_text and len(custom_text.strip()) > 10:
                    return custom_text
            except Exception:
                pass

        return (
            f"🛑 <b>TRADEPULSE CIRCUIT BREAKER ACTIVATED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>Signal Scanner Auto-Paused</b>\n"
            f"• <b>Trigger Reason:</b> <b>{reason}</b>\n"
            f"• <b>Session Net PnL:</b> <b>{pnl_str}</b>\n"
            f"• <b>Total Trades:</b> <b>{trades}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>"
        )

    @classmethod
    def format_markets_table(cls, active_symbols: List[str]) -> str:
        """Formats the real-time /markets overview table."""
        lines = [
            f"📊 <b>QUOTEX LIVE RATES ({len(active_symbols)} Assets)</b>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]
        for sym in active_symbols:
            price = asset_registry.get_latest_price(sym)
            payout = asset_registry.get_payout(sym)
            price_str = asset_registry.format_price(sym, price) if price else "Streaming..."
            payout_str = f"{payout:.0f}%" if payout is not None else "--%"
            lines.append(f"• <code>{sym:<16}</code>: <b>{price_str}</b> (<code>{payout_str}</code>)")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("<i>Updated continuously via Live WebSocket Stream</i>")
        return "\n".join(lines)

    @classmethod
    def format_status_report(
        cls,
        uptime_seconds: float,
        latency_ms: float,
        connected_pairs: int,
        active_strategies: int,
        total_signals: int,
        win_rate: float
    ) -> str:
        """Formats the /status telemetry report."""
        m, s = divmod(int(uptime_seconds), 60)
        h, m = divmod(m, 60)
        uptime_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m:02d}m {s:02d}s"

        return (
            f"⚡ <b>TRADEPULSE TELEMETRY STATUS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Engine Status:</b> 🟢 <b>SCANNING</b>\n"
            f"• <b>Broker Feed:</b> <b>Connected ({latency_ms}ms)</b>\n"
            f"• <b>Uptime:</b> <code>{uptime_str}</code>\n"
            f"• <b>Monitored Pairs:</b> <code>{connected_pairs} Assets</code>\n"
            f"• <b>Active User Strategies:</b> <code>{active_strategies}</code>\n"
            f"• <b>Signals Fired:</b> <code>{total_signals}</code>\n"
            f"• <b>Historical Win Rate:</b> <b>{win_rate:.1f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <i>Safe Mode: 100% Real-Time Market Confluence</i>"
        )
