from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class TelegramMessageFormatter:
    """
    Renders clean, professional, concise, and high-impact Telegram messages and interactive sub-views.
    Uses Telegram HTML formatting with sleek interactive keyboard layouts.
    """

    @classmethod
    def format_main_signal(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        """
        Formats a sleek, high-impact premium VIP signal card.
        """
        sig_id = signal.get("id", "")
        asset = signal.get("asset_symbol", "EUR/USD (OTC)")
        direction = signal.get("direction", "DOWN").upper()
        ref_price = signal.get("reference_price", 0.0)
        pattern_name = signal.get("pattern_name", "Pattern Type 14")
        ai_score = signal.get("ai_score", 95)
        strength = signal.get("signal_strength", "HIGH")
        status = signal.get("status", "ACTIVE")

        # Resolve timezone conversions for IST (UTC+5:30) and UTC
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        utc_tz = timezone.utc

        if isinstance(entry_time, datetime):
            entry_dt = entry_time if entry_time.tzinfo else entry_time.replace(tzinfo=utc_tz)
        else:
            entry_dt = datetime.now(utc_tz)

        if isinstance(expiry_time, datetime):
            expiry_dt = expiry_time if expiry_time.tzinfo else expiry_time.replace(tzinfo=utc_tz)
        else:
            expiry_dt = entry_dt + timedelta(minutes=1)

        entry_ist = entry_dt.astimezone(ist_tz).strftime("%H:%M:%S")
        expiry_ist = expiry_dt.astimezone(ist_tz).strftime("%H:%M:%S")

        entry_utc = entry_dt.astimezone(utc_tz).strftime("%H:%M:%S")
        expiry_utc = expiry_dt.astimezone(utc_tz).strftime("%H:%M:%S")

        is_call = direction in ["UP", "LONG", "BUY", "CALL"]
        dir_badge = "🟢 CALL / UP ⬆️" if is_call else "🔴 PUT / DOWN ⬇️"

        text = (
            f"⚡ <b>TRADEPULSE AI SIGNAL ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Asset:</b> <code>{asset}</code>\n"
            f"🎯 <b>Action:</b> <b>{dir_badge}</b>\n"
            f"⏱ <b>Expiry:</b> <b>1 MINUTE</b>\n"
            f"💵 <b>Entry Price:</b> <code>{ref_price}</code>\n"
            f"🇮🇳 <b>Window (IST):</b> <code>{entry_ist}</code> ➔ <code>{expiry_ist}</code>\n"
            f"🌐 <b>Window (UTC):</b> <code>{entry_utc}</code> ➔ <code>{expiry_utc}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Pattern:</b> {pattern_name}\n"
            f"🧠 <b>AI Confidence:</b> <b>{ai_score}% ({strength})</b>\n"
            f"📌 <b>Status:</b> 🟢 {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Click buttons below for live multi-factor analysis:</i>"
        )

        keyboard = [
            [
                {"text": "🧠 AI Analysis", "callback_data": f"ai:{sig_id}"},
                {"text": "📊 Technicals", "callback_data": f"tech:{sig_id}"}
            ],
            [
                {"text": "📈 Live Price", "callback_data": f"live:{sig_id}"},
                {"text": "📋 Audit Details", "callback_data": f"details:{sig_id}"}
            ]
        ]

        return text, keyboard

    @classmethod
    def format_ai_analysis_view(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        ai = signal.get("ai_analysis", {})
        asset = signal.get("asset_symbol", "EUR/USD (OTC)")

        bias = ai.get("bias", "BEARISH")
        score = ai.get("score", 88)
        conf = ai.get("confidence", "HIGH")
        trend = ai.get("trend_assessment", "Momentum continuation on 1M OTC candles")
        mom = ai.get("momentum_assessment", "RSI divergence confirms directional push")
        vol = ai.get("volume_assessment", "Volume is 135% of 20-period moving average")
        structure = ai.get("structure_assessment", "Clean breakout at key price level")
        entry_q = ai.get("entry_quality", "Immediate continuation close")
        risk_q = ai.get("risk_assessment", "Low to Moderate Risk")
        reasoning = ai.get("reasoning", "Strong multi-timeframe pattern confirmation with quantitative algorithmic backing.")
        risks = ai.get("risks", ["OTC micro-volatility spike", "Retest of broken level"])

        risks_formatted = "\n".join([f"• {r}" for r in risks])

        text = (
            f"🧠 <b>AI RESEARCH BREAKDOWN</b>\n"
            f"💎 <b>{asset}</b> | Score: <b>{score}% ({conf} Confidence)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Directional Bias:</b> {bias}\n"
            f"📈 <b>Trend Assessment:</b> {trend}\n"
            f"⚡ <b>Momentum:</b> {mom}\n"
            f"📊 <b>Volume:</b> {vol}\n"
            f"🏗 <b>Structure:</b> {structure}\n"
            f"🎯 <b>Entry Quality:</b> {entry_q}\n"
            f"🛡 <b>Risk Rating:</b> {risk_q}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Algorithmic Reasoning:</b>\n{reasoning}\n\n"
            f"⚠️ <b>Key Risks:</b>\n{risks_formatted}"
        )

        keyboard = [
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard

    @classmethod
    def format_technicals_view(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        tech = signal.get("technical_snapshot", {})
        asset = signal.get("asset_symbol", "EUR/USD (OTC)")
        timeframe = signal.get("timeframe", "1M")

        rsi = tech.get("rsi", "N/A")
        macd = tech.get("macd", {})
        ema_fast = tech.get("ema_fast", "N/A")
        ema_slow = tech.get("ema_slow", "N/A")
        bb = tech.get("bollinger_bands", {})
        vol_ratio = tech.get("volume_ratio", 1.0)
        supports = tech.get("support_levels", [])
        resistances = tech.get("resistance_levels", [])

        supp_str = ", ".join(str(s) for s in supports) if supports else "Dynamic Support"
        res_str = ", ".join(str(r) for r in resistances) if resistances else "Dynamic Resistance"

        text = (
            f"📊 <b>TECHNICAL SNAPSHOT ({timeframe})</b>\n"
            f"💎 <b>{asset}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>RSI (14):</b> <code>{rsi}</code>\n"
            f"• <b>MACD:</b> {macd.get('macd', 'N/A')} | Sig: {macd.get('signal', 'N/A')}\n"
            f"• <b>EMA Fast (9):</b> <code>{ema_fast}</code>\n"
            f"• <b>EMA Slow (21):</b> <code>{ema_slow}</code>\n"
            f"• <b>Bollinger Bands:</b> Upper {bb.get('upper', 'N/A')} | Lower {bb.get('lower', 'N/A')}\n"
            f"• <b>Relative Volume:</b> {vol_ratio}x of 20 SMA\n"
            f"• <b>Key Supports:</b> <code>{supp_str}</code>\n"
            f"• <b>Key Resistances:</b> <code>{res_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = [
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard

    @classmethod
    def format_live_signal_view(cls, signal: Dict[str, Any], current_price: float) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        asset = signal.get("asset_symbol", "EUR/USD (OTC)")
        direction = signal.get("direction", "DOWN")
        ref_price = signal.get("reference_price", 0.0)
        status = signal.get("status", "ACTIVE")

        diff = current_price - ref_price
        diff_pct = (diff / ref_price * 100) if ref_price > 0 else 0.0

        if direction in ["DOWN", "SHORT", "SELL", "PUT"]:
            in_profit = current_price < ref_price
        else:
            in_profit = current_price > ref_price

        profit_indicator = "🟢 IN PROFIT" if in_profit else "🔴 OUT OF MONEY"

        text = (
            f"📈 <b>LIVE PRICE TRACKING</b>\n"
            f"💎 <b>{asset}</b> | Direction: <b>{direction}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Entry Price:</b> <code>{ref_price}</code>\n"
            f"⚡ <b>Live Price:</b>  <code>{current_price}</code>\n"
            f"📊 <b>Delta:</b> {diff:+.5f} ({diff_pct:+.2f}%)\n"
            f"🎯 <b>Status:</b> <b>{profit_indicator}</b> ({status})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Live ticks are updated continuously.</i>"
        )

        keyboard = [
            [{"text": "🔄 Refresh Price", "callback_data": f"live:{sig_id}"}],
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard

    @classmethod
    def format_full_details_view(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        pattern_name = signal.get("pattern_name", "Quotex 1M OTC Momentum")
        version = signal.get("pattern_version", 1)
        market = signal.get("market_id", "digital_options")
        timeframe = signal.get("timeframe", "1M")

        text = (
            f"📋 <b>STRATEGY & SIGNAL AUDIT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Signal ID:</b> <code>{sig_id[:12]}...</code>\n"
            f"• <b>Pattern:</b> {pattern_name} (v{version})\n"
            f"• <b>Market Type:</b> {market}\n"
            f"• <b>Timeframe:</b> {timeframe}\n"
            f"• <b>Duration:</b> {signal.get('duration_minutes', 1)} Minute(s)\n"
            f"• <b>Created At:</b> {str(signal.get('created_at', ''))[:19]}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = [
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard
