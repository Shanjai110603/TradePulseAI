from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class TelegramMessageFormatter:
    """
    Renders clean, professional, concise Telegram messages and detailed sub-views.
    Uses Telegram HTML / Markdown formatting with interactive keyboard layouts.
    """

    @classmethod
    def format_main_signal(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        """
        Formats concise, high-impact main signal alert as specified in prompt.
        """
        sig_id = signal.get("id", "")
        asset = signal.get("asset_symbol", "EUR/USD")
        direction = signal.get("direction", "DOWN").upper()
        ref_price = signal.get("reference_price", 0.0)
        pattern_name = signal.get("pattern_name", "Pattern Type 14")
        ai_score = signal.get("ai_score", 85)
        strength = signal.get("signal_strength", "HIGH")
        status = signal.get("status", "ACTIVE")
        duration = signal.get("duration_minutes", 5)

        entry_time = signal.get("entry_time")
        if isinstance(entry_time, datetime):
            entry_str = entry_time.strftime("%H:%M:%S")
        else:
            entry_str = str(entry_time)[11:19] if entry_time else "10:35:20"

        expiry_time = signal.get("expiry_time")
        if isinstance(expiry_time, datetime):
            expiry_str = expiry_time.strftime("%H:%M:%S")
        else:
            expiry_str = str(expiry_time)[11:19] if expiry_time else "10:40:20"

        dir_emoji = "🔴" if direction in ["DOWN", "SHORT", "SELL"] else "🟢"
        dir_text = "DOWN" if direction in ["DOWN", "SHORT", "SELL"] else "UP"

        text = (
            f"🚨 <b>NEW RESEARCH SIGNAL</b>\n\n"
            f"💎 <b>{asset}</b>\n\n"
            f"{dir_emoji} <b>{dir_text}</b>\n\n"
            f"💰 <b>Reference Price</b>\n<code>{ref_price}</code>\n\n"
            f"⏰ <b>Entry</b>\n<code>{entry_str}</code>\n\n"
            f"⌛ <b>Expiry</b>\n<code>{expiry_str}</code>\n\n"
            f"⏱ <b>Duration</b>\n{duration} Minutes\n\n"
            f"🔷 <b>Pattern</b>\n{pattern_name}\n\n"
            f"🧠 <b>AI Score</b>\n{ai_score}/100\n\n"
            f"📊 <b>Signal Strength</b>\n{strength}\n\n"
            f"📌 <b>Status</b>\n{status}"
        )

        keyboard = [
            [
                {"text": "🧠 AI Analysis", "callback_data": f"ai:{sig_id}"},
                {"text": "📊 Technicals", "callback_data": f"tech:{sig_id}"}
            ],
            [
                {"text": "📈 Live Signal", "callback_data": f"live:{sig_id}"},
                {"text": "📋 Full Details", "callback_data": f"details:{sig_id}"}
            ],
            [
                {"text": "🔔 Follow Signal", "callback_data": f"follow:{sig_id}"},
                {"text": "🔕 Mute", "callback_data": f"mute:{sig_id}"}
            ]
        ]

        return text, keyboard

    @classmethod
    def format_ai_analysis_view(cls, signal: Dict[str, Any]) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        ai = signal.get("ai_analysis", {})
        asset = signal.get("asset_symbol", "EUR/USD")

        bias = ai.get("bias", "BEARISH")
        score = ai.get("score", 85)
        conf = ai.get("confidence", "HIGH")
        trend = ai.get("trend_assessment", "Bearish momentum on 1M/5M")
        mom = ai.get("momentum_assessment", "RSI confirms downward pressure")
        vol = ai.get("volume_assessment", "Volume is 125% of average")
        structure = ai.get("structure_assessment", "Confirmed support breakdown")
        entry_q = ai.get("entry_quality", "Optimal breakout close entry")
        risk_q = ai.get("risk_assessment", "Moderate risk, strict invalidation")
        reasoning = ai.get("reasoning", "Pattern confirmed with high confluence.")
        risks = ai.get("risks", ["Spread expansion", "Macro news volatility"])

        risks_formatted = "\n".join([f"• {r}" for r in risks])

        text = (
            f"🧠 <b>AI RESEARCH ANALYSIS</b>\n"
            f"💎 <b>{asset}</b> | Score: <b>{score}/100</b> ({conf} Confidence)\n\n"
            f"🎯 <b>Bias:</b> {bias}\n"
            f"📈 <b>Trend:</b> {trend}\n"
            f"⚡ <b>Momentum:</b> {mom}\n"
            f"📊 <b>Volume:</b> {vol}\n"
            f"🏗 <b>Structure:</b> {structure}\n"
            f"🎯 <b>Entry Quality:</b> {entry_q}\n"
            f"🛡 <b>Risk Rating:</b> {risk_q}\n\n"
            f"💡 <b>AI Reasoning:</b>\n{reasoning}\n\n"
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
        asset = signal.get("asset_symbol", "EUR/USD")
        timeframe = signal.get("timeframe", "1M")

        rsi = tech.get("rsi", "N/A")
        macd = tech.get("macd", {})
        ema_fast = tech.get("ema_fast", "N/A")
        ema_slow = tech.get("ema_slow", "N/A")
        bb = tech.get("bollinger_bands", {})
        atr = tech.get("atr", "N/A")
        adx = tech.get("adx", "N/A")
        stoch = tech.get("stochastic", {})
        vol_ratio = tech.get("volume_ratio", 1.0)
        supports = tech.get("support_levels", [])
        resistances = tech.get("resistance_levels", [])

        supp_str = ", ".join(str(s) for s in supports) if supports else "None"
        res_str = ", ".join(str(r) for r in resistances) if resistances else "None"

        text = (
            f"📊 <b>TECHNICAL SNAPSHOT ({timeframe})</b>\n"
            f"💎 <b>{asset}</b>\n\n"
            f"• <b>RSI (14):</b> {rsi}\n"
            f"• <b>MACD:</b> {macd.get('macd', 'N/A')} | Signal: {macd.get('signal', 'N/A')}\n"
            f"• <b>EMA Fast (9):</b> {ema_fast}\n"
            f"• <b>EMA Slow (21):</b> {ema_slow}\n"
            f"• <b>Bollinger Bands:</b> Upper {bb.get('upper', 'N/A')} | Lower {bb.get('lower', 'N/A')}\n"
            f"• <b>ATR (14):</b> {atr}\n"
            f"• <b>ADX (14):</b> {adx}\n"
            f"• <b>Stochastic:</b> %K {stoch.get('k', 'N/A')} | %D {stoch.get('d', 'N/A')}\n"
            f"• <b>Volume Ratio:</b> {vol_ratio}x of 20 SMA\n"
            f"• <b>Key Supports:</b> {supp_str}\n"
            f"• <b>Key Resistances:</b> {res_str}"
        )

        keyboard = [
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard

    @classmethod
    def format_live_signal_view(cls, signal: Dict[str, Any], current_price: float) -> Tuple[str, List[List[Dict[str, str]]]]:
        sig_id = signal.get("id", "")
        asset = signal.get("asset_symbol", "EUR/USD")
        direction = signal.get("direction", "DOWN")
        ref_price = signal.get("reference_price", 0.0)
        status = signal.get("status", "ACTIVE")

        diff = current_price - ref_price
        diff_pct = (diff / ref_price * 100) if ref_price > 0 else 0.0

        if direction in ["DOWN", "SHORT", "SELL"]:
            in_profit = current_price < ref_price
        else:
            in_profit = current_price > ref_price

        profit_indicator = "🟢 IN PROFIT ZONE" if in_profit else "🔴 OUT OF PROFIT ZONE"

        text = (
            f"📈 <b>LIVE SIGNAL TRACKING</b>\n"
            f"💎 <b>{asset}</b> | Direction: <b>{direction}</b>\n\n"
            f"💰 <b>Reference Price:</b> <code>{ref_price}</code>\n"
            f"⚡ <b>Current Price:</b> <code>{current_price}</code>\n"
            f"📊 <b>Delta:</b> {diff:+.5f} ({diff_pct:+.2f}%)\n"
            f"🎯 <b>Status:</b> {status} ({profit_indicator})\n\n"
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
        pattern_name = signal.get("pattern_name", "")
        version = signal.get("pattern_version", 1)
        market = signal.get("market_id", "")
        timeframe = signal.get("timeframe", "")

        text = (
            f"📋 <b>FULL AUDIT DETAILS</b>\n\n"
            f"• <b>Signal ID:</b> <code>{sig_id}</code>\n"
            f"• <b>Pattern:</b> {pattern_name} (v{version})\n"
            f"• <b>Market Type:</b> {market}\n"
            f"• <b>Timeframe:</b> {timeframe}\n"
            f"• <b>SL / TP Configured:</b> {signal.get('stop_loss', 'N/A')} / {signal.get('tp1', 'N/A')}\n"
            f"• <b>Risk/Reward:</b> {signal.get('risk_reward_ratio', 'N/A')}\n"
            f"• <b>Created At:</b> {str(signal.get('created_at', ''))[:19]}\n"
        )

        keyboard = [
            [{"text": "⬅️ Back to Signal", "callback_data": f"back:{sig_id}"}]
        ]
        return text, keyboard
