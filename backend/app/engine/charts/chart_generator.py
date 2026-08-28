import os
import math
import functools
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from app.engine.market_data.base import Candle


@functools.lru_cache(maxsize=32)
def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Robust TrueType font loader with bundled repository fonts & RAM caching"""
    base_dir = os.path.dirname(__file__)
    bundled_bold = os.path.join(base_dir, "fonts", "Arial-Bold.ttf")
    bundled_reg = os.path.join(base_dir, "fonts", "Arial-Regular.ttf")

    if bold and os.path.exists(bundled_bold):
        try:
            return ImageFont.truetype(bundled_bold, size)
        except Exception:
            pass
    elif not bold and os.path.exists(bundled_reg):
        try:
            return ImageFont.truetype(bundled_reg, size)
        except Exception:
            pass

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _format_price(price: float, asset: str) -> str:
    """Formats price decimals according to asset currency/crypto standard"""
    if "JPY" in asset:
        return f"{price:.3f}"
    elif "BTC" in asset or "ETH" in asset:
        return f"{price:.2f}"
    return f"{price:.5f}"


class TradeChartGenerator:
    """
    Renders high-definition (1280x720 HD) TradingView-style candlestick charts
    of the actual trade setup, including live candlesticks, SMC 10 Line,
    Horizontal breakout levels, and bold entry trigger markers.
    """

    @classmethod
    def generate_chart(
        cls,
        candles: List[Candle],
        signal_data: Dict[str, Any],
        output_dir: str = "uploads/signals"
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        sig_id = signal_data.get("id", f"sig_{int(datetime.now().timestamp())}")
        output_path = os.path.join(output_dir, f"{sig_id}.png")

        width = 1280
        height = 720
        asset = signal_data.get("asset_symbol", "EUR/USD (OTC)")

        # Fonts
        font_logo = _load_font(20, bold=True)
        font_asset = _load_font(26, bold=True)
        font_header_sub = _load_font(16, bold=False)
        font_strategy = _load_font(19, bold=True)
        font_badge = _load_font(17, bold=True)
        font_entry = _load_font(18, bold=True)
        font_axis = _load_font(15, bold=False)
        font_footer = _load_font(14, bold=False)

        # 1. Canvas with Sleek Deep Dark Theme
        img = Image.new("RGB", (width, height), color=(10, 14, 22))
        draw = ImageDraw.Draw(img)

        # Gradient Background
        for y in range(height):
            ratio = y / height
            r = int(10 + ratio * 8)
            g = int(14 + ratio * 8)
            b = int(22 + ratio * 12)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Chart Layout Geometry - Full Height & Width Utilization
        chart_top = 100
        chart_bottom = height - 60
        chart_left = 60
        chart_right = width - 125
        chart_h = chart_bottom - chart_top
        chart_w = chart_right - chart_left

        # Show 18 to 20 recent candles for wide, bold, non-flat visibility
        display_candles = candles[-20:] if len(candles) >= 20 else candles
        if not display_candles:
            display_candles = [
                Candle(timestamp=int(datetime.now().timestamp()), open=1.0850, high=1.0855, low=1.0848, close=1.0852, volume=100.0)
            ]

        num_candles = len(display_candles)
        ref_price = float(signal_data.get("reference_price", display_candles[-1].close))
        sup_val = float(signal_data["support_level"]) if signal_data.get("support_level") else None
        res_val = float(signal_data["resistance_level"]) if signal_data.get("resistance_level") else None

        # 2. Dynamic Full-Canvas Auto-Fitting to Visible Candles
        min_c = min(c.low for c in display_candles)
        max_c = max(c.high for c in display_candles)
        candle_span = max(max_c - min_c, 0.00005)

        # Dynamic vertical padding (14%) based on visible candle excursion
        pad = candle_span * 0.14
        y_min = min_c - pad
        y_max = max_c + pad

        # If key levels are within close proximity, expand slightly; otherwise clamp to keep candles tall
        if sup_val and (min_c - pad * 2) <= sup_val <= (max_c + pad * 2):
            y_min = min(y_min, sup_val - pad * 0.5)
        if res_val and (min_c - pad * 2) <= res_val <= (max_c + pad * 2):
            y_max = max(y_max, res_val + pad * 0.5)

        p_range = max(y_max - y_min, 0.00001)

        def price_to_y(p: float) -> int:
            norm = (p - y_min) / p_range
            return int(chart_bottom - (norm * chart_h))

        # 3. Horizontal Grid Lines & Right Price Scale
        grid_count = 6
        for i in range(grid_count + 1):
            p_val = y_min + (i * (p_range / grid_count))
            y_pos = price_to_y(p_val)
            # Subtle Grid Line
            draw.line([(chart_left, y_pos), (chart_right, y_pos)], fill=(22, 30, 44), width=1)
            # Y-Axis Price Label
            draw.text((chart_right + 12, y_pos - 8), _format_price(p_val, asset), fill=(140, 165, 195), font=font_axis)

        # 4. Watermark in Chart Center Background
        draw.text((chart_left + 20, chart_top + 20), f"{asset} • 1M OTC CANDLESTICK STREAM", fill=(18, 25, 38), font=_load_font(26, bold=True))

        # 5. SMC 10 Moving Average Line (Glowing Amber Curve)
        if len(candles) >= 5:
            closes = [c.close for c in candles]
            smc_points = []
            candle_step = chart_w / max(num_candles, 1)
            start_offset = len(candles) - num_candles

            for idx, c in enumerate(display_candles):
                c_idx = start_offset + idx
                lookback = min(c_idx + 1, 10)
                smc_val = sum(closes[c_idx - lookback + 1 : c_idx + 1]) / float(lookback)
                cx = int(chart_left + (idx + 0.5) * candle_step)
                cy = price_to_y(smc_val)
                smc_points.append((cx, cy))

            if len(smc_points) >= 2:
                for j in range(len(smc_points) - 1):
                    # Glow ribbon effect
                    draw.line([smc_points[j], smc_points[j + 1]], fill=(255, 183, 3), width=3)

        # 6. Horizontal Support / Resistance Breakout Level
        level_val = sup_val or res_val
        if level_val:
            ly = price_to_y(float(level_val))
            if chart_top <= ly <= chart_bottom:
                # Dashed Cyan Line
                for dx in range(chart_left, chart_right, 18):
                    draw.line([(dx, ly), (min(dx + 10, chart_right), ly)], fill=(0, 229, 255), width=2)
                # Level Tag on Right Axis
                draw.rectangle([(chart_right + 8, ly - 11), (chart_right + 108, ly + 11)], fill=(0, 180, 216))
                draw.text((chart_right + 12, ly - 8), "KEY LEVEL", fill=(0, 0, 0), font=_load_font(13, bold=True))

        # 7. Candlesticks Rendering (Bold, Wide, Vibrant Tall Bodies)
        candle_step = chart_w / max(num_candles, 1)
        body_w = max(int(candle_step * 0.76), 14)

        for i, c in enumerate(display_candles):
            cx = int(chart_left + (i + 0.5) * candle_step)
            is_bull = c.close >= c.open

            # Vibrant TradingView colors
            c_fill = (0, 230, 118) if is_bull else (255, 59, 78)
            c_border = (0, 255, 140) if is_bull else (255, 82, 102)

            hy = price_to_y(c.high)
            ly = price_to_y(c.low)
            oy = price_to_y(c.open)
            cy = price_to_y(c.close)

            # Center Wick (2px crisp)
            draw.line([(cx, hy), (cx, ly)], fill=c_border, width=2)

            # Solid Candle Body with healthy min height
            top_y = min(oy, cy)
            bot_y = max(oy, cy)
            if bot_y - top_y < 6:
                bot_y = top_y + 6

            x1 = cx - body_w // 2
            x2 = cx + body_w // 2
            draw.rectangle([(x1, top_y), (x2, bot_y)], fill=c_fill, outline=c_border, width=1)

            # Volume Bars at bottom
            vol_h = min(int((c.volume / 2500.0) * 35), 35)
            draw.rectangle([(x1, chart_bottom - vol_h), (x2, chart_bottom)], fill=(28, 38, 54))

            # Bottom X-Axis Time Labels (every 4th candle)
            if i % 4 == 0 or i == num_candles - 1:
                try:
                    c_dt = datetime.fromtimestamp(c.timestamp, tz=timezone.utc)
                    t_str = c_dt.strftime("%H:%M")
                    draw.text((cx - 15, chart_bottom + 10), t_str, fill=(110, 135, 165), font=_load_font(13))
                except Exception:
                    pass

        # 8. Entry Trigger Marker (Last Candle)
        trigger_cx = int(chart_left + (num_candles - 0.5) * candle_step)
        direction = signal_data.get("direction", "DOWN").upper()
        is_call = direction in ["UP", "LONG", "BUY", "CALL"]
        trigger_c = display_candles[-1]

        action_color = (0, 230, 118) if is_call else (255, 45, 85)
        action_text = "CALL (BUY)" if is_call else "PUT (SELL)"
        formatted_ref = _format_price(ref_price, asset)

        if is_call:
            # Arrow pointing UP below candle
            tip_y = price_to_y(trigger_c.low) + 16
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 14, tip_y + 18),
                (trigger_cx + 14, tip_y + 18)
            ], fill=action_color)
            # Floating Pill Badge
            box_top = tip_y + 22
            draw.rectangle([(trigger_cx - 105, box_top), (trigger_cx + 105, box_top + 34)], fill=action_color)
            draw.text((trigger_cx - 96, box_top + 6), f"{action_text} @ {formatted_ref}", fill=(0, 0, 0), font=font_entry)
        else:
            # Arrow pointing DOWN above candle
            tip_y = price_to_y(trigger_c.high) - 16
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 14, tip_y - 18),
                (trigger_cx + 14, tip_y - 18)
            ], fill=action_color)
            # Floating Pill Badge
            box_top = max(tip_y - 56, chart_top + 8)
            draw.rectangle([(trigger_cx - 105, box_top), (trigger_cx + 105, box_top + 34)], fill=action_color)
            draw.text((trigger_cx - 96, box_top + 6), f"{action_text} @ {formatted_ref}", fill=(255, 255, 255), font=font_entry)

        # 9. Header Styling
        pattern_name = signal_data.get("pattern_name", "Pattern Type 14")
        ai_score = signal_data.get("ai_score", 92)

        # Header Bar Background
        draw.rectangle([(0, 0), (width, 84)], fill=(14, 19, 30))
        draw.line([(0, 84), (width, 84)], fill=(28, 38, 56), width=2)

        # Logo Badge
        draw.rectangle([(20, 18), (195, 66)], fill=(0, 229, 255))
        draw.text((32, 28), "TRADEPULSE AI", fill=(0, 0, 0), font=font_logo)

        # Asset & Live Price
        draw.text((215, 24), f"{asset}", fill=(255, 255, 255), font=font_asset)
        draw.rectangle([(445, 26), (530, 60)], fill=(22, 32, 48))
        draw.text((455, 32), "1M OTC", fill=(0, 229, 255), font=font_header_sub)
        draw.text((545, 25), f"Live: {formatted_ref}", fill=(0, 230, 118), font=font_asset)

        # Right Header Strategy Info & AI Score
        draw.text((width - 490, 16), f"Strategy: {pattern_name}", fill=(255, 215, 0), font=font_strategy)
        draw.rectangle([(width - 490, 46), (width - 140, 76)], fill=(0, 229, 255))
        draw.text((width - 480, 50), f"AI SCORE: {ai_score}% (HIGH ACCURACY)", fill=(0, 0, 0), font=font_badge)

        # 10. Footer Bar with Clean Graphical Legend (No Unicode Squares)
        draw.rectangle([(0, height - 38), (width, height)], fill=(10, 14, 22))
        draw.line([(0, height - 38), (width, height - 38)], fill=(24, 32, 46), width=1)

        # SMC Line Dot + Text
        draw.ellipse([(25, height - 26), (37, height - 14)], fill=(255, 183, 3))
        draw.text((44, height - 26), "SMC 10 Line", fill=(160, 180, 205), font=font_footer)

        # Key Level Bar + Text
        draw.rectangle([(160, height - 22), (185, height - 18)], fill=(0, 229, 255))
        draw.text((192, height - 26), "Key Breakdown / Support Level", fill=(160, 180, 205), font=font_footer)

        # Expiry Badge
        draw.ellipse([(440, height - 26), (452, height - 14)], fill=(0, 230, 118))
        draw.ellipse([(458, height - 26), (470, height - 14)], fill=(255, 45, 85))
        draw.text((478, height - 26), "Live Trade Setup (1 MINUTE Expiry)", fill=(160, 180, 205), font=font_footer)

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((width - 340, height - 26), f"Live Quotex Stream • {now_str}", fill=(110, 130, 155), font=font_footer)

        # Save Image
        img.save(output_path, "PNG", quality=95)
        return output_path
