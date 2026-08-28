from datetime import datetime, timezone, timedelta
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
        entry_time = signal.get("entry_time")
        expiry_time = signal.get("expiry_time")

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

        feed_source = signal.get("feed_source") or "Quotex Live Relay"

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
            f"📡 <b>Feed Source:</b> <code>{feed_source}</code>\n"
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

    # ---------------------------------------------------------
    # Currency Categories & Real-Time Monitoring Views
    # ---------------------------------------------------------

    QUOTEX_CATEGORIES = {
        "forex_otc": {
            "title": "💱 Forex OTC Pairs",
            "assets": [
                ("EUR/USD (OTC)", "EURUSD_otc", "95%"),
                ("GBP/USD (OTC)", "GBPUSD_otc", "95%"),
                ("USD/BRL (OTC)", "USDBRL_otc", "95%"),
                ("EUR/NZD (OTC)", "EURNZD_otc", "95%"),
                ("NZD/CAD (OTC)", "NZDCAD_otc", "93%"),
                ("USD/ARS (OTC)", "USDARS_otc", "93%"),
                ("USD/INR (OTC)", "USDINR_otc", "88%"),
                ("USD/JPY (OTC)", "USDJPY_otc", "82%"),
                ("USD/CHF (OTC)", "USDCHF_otc", "85%"),
                ("AUD/USD (OTC)", "AUDUSD_otc", "85%"),
                ("USD/CAD (OTC)", "USDCAD_otc", "85%"),
                ("NZD/USD (OTC)", "NZDUSD_otc", "93%"),
                ("EUR/GBP (OTC)", "EURGBP_otc", "85%"),
                ("EUR/JPY (OTC)", "EURJPY_otc", "85%"),
                ("GBP/JPY (OTC)", "GBPJPY_otc", "85%"),
                ("AUD/CAD (OTC)", "AUDCAD_otc", "85%"),
                ("USD/TRY (OTC)", "USDTRY_otc", "85%"),
                ("USD/MXN (OTC)", "USDMXN_otc", "85%"),
                ("USD/EGP (OTC)", "USDEGP_otc", "89%"),
                ("USD/IDR (OTC)", "USDIDR_otc", "88%"),
                ("USD/PHP (OTC)", "USDPHP_otc", "88%"),
            ]
        },
        "crypto_otc": {
            "title": "🪙 Crypto OTC Pairs",
            "assets": [
                ("BTC/USDT (OTC)", "BTCUSD_otc", "86%"),
                ("ETH/USDT (OTC)", "ETHUSD_otc", "84%"),
                ("SOL/USDT (OTC)", "SOLUSD_otc", "82%"),
                ("XRP/USDT (OTC)", "XRPUSD_otc", "82%"),
                ("LTC/USDT (OTC)", "LTCUSD_otc", "80%"),
                ("DOGE/USDT (OTC)", "DOGEUSD_otc", "80%"),
            ]
        },
        "commodities": {
            "title": "🥇 Commodities OTC",
            "assets": [
                ("GOLD (OTC)", "XAUUSD_otc", "90%"),
                ("SILVER (OTC)", "XAGUSD_otc", "88%"),
                ("US CRUDE (OTC)", "UKBrent_otc", "85%"),
            ]
        },
        "forex_live": {
            "title": "🌍 Live Standard Forex",
            "assets": [
                ("EUR/USD", "EURUSD", "82%"),
                ("GBP/USD", "GBPUSD", "82%"),
                ("USD/JPY", "USDJPY", "80%"),
                ("AUD/USD", "AUDUSD", "80%"),
                ("USD/CAD", "USDCAD", "80%"),
                ("USD/CHF", "USDCHF", "80%"),
            ]
        }
    }

    @classmethod
    def format_currency_categories_menu(cls) -> Tuple[str, List[List[Dict[str, str]]]]:
        """Renders the top-level currency categories menu."""
        text = (
            "🏛️ <b>QUOTEX LIVE CURRENCY & TRADE DIRECTORY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Select a market category below to explore all active trade assets, view real-time prices & payouts, and start monitoring any pair live in the bot:\n\n"
            "• 💱 <b>Forex OTC:</b> 21 High-payout 24/7 OTC Pairs\n"
            "• 🪙 <b>Crypto OTC:</b> BTC, ETH, SOL, XRP, DOGE\n"
            "• 🥇 <b>Commodities:</b> Gold, Silver, Crude Oil\n"
            "• 🌍 <b>Live Forex:</b> Standard Interbank Market Pairs\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ <i>Data Stream: 100% Real-Time Quotex Broker Feed</i>"
        )

        keyboard = [
            [
                {"text": "💱 Forex OTC (21 Pairs)", "callback_data": "curr_cat:forex_otc:0"},
                {"text": "🪙 Crypto OTC", "callback_data": "curr_cat:crypto_otc:0"}
            ],
            [
                {"text": "🥇 Commodities OTC", "callback_data": "curr_cat:commodities:0"},
                {"text": "🌍 Live Forex Pairs", "callback_data": "curr_cat:forex_live:0"}
            ],
            [
                {"text": "🔄 Refresh All Rates", "callback_data": "curr_home"}
            ]
        ]
        return text, keyboard

    @classmethod
    def format_currency_list(cls, cat_key: str, page: int = 0) -> Tuple[str, List[List[Dict[str, str]]]]:
        """Renders a paginated list of currency pairs for a chosen category."""
        category = cls.QUOTEX_CATEGORIES.get(cat_key, cls.QUOTEX_CATEGORIES["forex_otc"])
        title = category["title"]
        all_assets = category["assets"]

        page_size = 6
        total_pages = (len(all_assets) + page_size - 1) // page_size
        page = max(0, min(page, total_pages - 1))
        start_idx = page * page_size
        page_assets = all_assets[start_idx : start_idx + page_size]

        text = (
            f"📊 <b>{title.upper()} (Page {page + 1}/{total_pages})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Click on any asset below to open its <b>Real-Time Live Monitor</b>, view candlestick stats, and enable institutional signal alerts:\n\n"
        )

        for name, code, payout in page_assets:
            text += f"• <b>{name}</b> ➔ Payout: <code>{payout}</code>\n"

        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Tap any pair below to inspect and monitor:</i>"
        )

        keyboard = []
        # Build 2-buttons-per-row for asset selection
        for i in range(0, len(page_assets), 2):
            row = []
            row.append({
                "text": f"📈 {page_assets[i][0]} ({page_assets[i][2]})",
                "callback_data": f"curr_sel:{page_assets[i][1]}"
            })
            if i + 1 < len(page_assets):
                row.append({
                    "text": f"📈 {page_assets[i+1][0]} ({page_assets[i+1][2]})",
                    "callback_data": f"curr_sel:{page_assets[i+1][1]}"
                })
            keyboard.append(row)

        # Pagination row
        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ Prev", "callback_data": f"curr_cat:{cat_key}:{page - 1}"})
        if page < total_pages - 1:
            nav_row.append({"text": "Next ➡️", "callback_data": f"curr_cat:{cat_key}:{page + 1}"})

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([{"text": "🔙 Back to Categories", "callback_data": "curr_home"}])
        return text, keyboard

    @classmethod
    def format_currency_monitor_card(
        cls,
        symbol_name: str,
        symbol_code: str,
        current_price: float,
        payout_pct: str,
        candles_count: int,
        latest_candle: Optional[Dict[str, Any]],
        tech_snapshot: Dict[str, Any]
    ) -> Tuple[str, List[List[Dict[str, str]]]]:
        """Renders the full real-time live monitor card for a chosen currency pair."""
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%H:%M:%S")
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S")

        rsi = tech_snapshot.get("rsi_14", 50.0)
        trend = tech_snapshot.get("trend", "Neutral")
        ema_20 = tech_snapshot.get("ema_20", current_price)
        momentum = tech_snapshot.get("momentum_state", "Moderate")
        volatility = tech_snapshot.get("atr_14", 0.00045)

        o = latest_candle.get("open", current_price) if latest_candle else current_price
        h = latest_candle.get("high", current_price) if latest_candle else current_price
        l = latest_candle.get("low", current_price) if latest_candle else current_price
        c = latest_candle.get("close", current_price) if latest_candle else current_price

        candle_color = "🟢 Bullish (Green)" if c >= o else "🔴 Bearish (Red)"

        text = (
            f"⚡ <b>LIVE ASSET MONITOR: {symbol_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Current Live Price:</b> <code>{current_price:.5f}</code>\n"
            f"💰 <b>Broker Payout Rate:</b> <b>{payout_pct}</b>\n"
            f"📡 <b>Feed Status:</b> 🟢 <b>Quotex Live Stream Active</b>\n"
            f"⏰ <b>Last Tick (IST):</b> <code>{now_ist}</code> | <b>(UTC):</b> <code>{now_utc}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕯️ <b>CURRENT 1M CANDLE:</b>\n"
            f"• <b>Open:</b> <code>{o:.5f}</code>  • <b>High:</b> <code>{h:.5f}</code>\n"
            f"• <b>Low:</b>  <code>{l:.5f}</code>  • <b>Close:</b> <code>{c:.5f}</code>\n"
            f"• <b>State:</b> {candle_color}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>TECHNICAL & SMC SNAPSHOT:</b>\n"
            f"• <b>RSI (14):</b> <code>{rsi:.1f}</code> ({'Overbought' if rsi > 70 else ('Oversold' if rsi < 30 else 'Balanced')})\n"
            f"• <b>EMA 20 Dynamic Level:</b> <code>{ema_20:.5f}</code>\n"
            f"• <b>Directional Bias:</b> <b>{trend.upper()}</b>\n"
            f"• <b>Momentum:</b> {momentum}\n"
            f"• <b>Buffer History:</b> <code>{candles_count}</code> live 1M bars cached\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <i>Tap buttons below to refresh live ticks, render a chart, or monitor alerts:</i>"
        )

        keyboard = [
            [
                {"text": "🔄 Refresh Live Price", "callback_data": f"curr_sel:{symbol_code}"},
                {"text": "📊 Generate 1M Chart", "callback_data": f"curr_chart:{symbol_code}"}
            ],
            [
                {"text": "🔔 Set Signal Alert for this Pair", "callback_data": f"curr_alert:{symbol_code}"}
            ],
            [
                {"text": "🔙 Back to Currency List", "callback_data": "curr_home"}
            ]
        ]
        return text, keyboard
