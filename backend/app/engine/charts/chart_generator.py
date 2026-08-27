import os
import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from app.engine.market_data.base import Candle


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Robust TrueType font loader across Linux Ubuntu Docker & Windows"""
    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "FreeSansBold.ttf" if bold else "FreeSans.ttf",
        "Ubuntu-Bold.ttf" if bold else "Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
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

        # Fonts
        font_logo = _load_font(20, bold=True)
        font_asset = _load_font(28, bold=True)
        font_header_sub = _load_font(18, bold=False)
        font_strategy = _load_font(20, bold=True)
        font_badge = _load_font(18, bold=True)
        font_entry = _load_font(18, bold=True)
        font_axis = _load_font(16, bold=False)
        font_footer = _load_font(15, bold=False)

        # Create canvas with rich dark background
        img = Image.new("RGB", (width, height), color=(10, 14, 22))
        draw = ImageDraw.Draw(img)

        # Subtle vertical gradient background
        for y in range(height):
            ratio = y / height
            r = int(9 + ratio * 8)
            g = int(13 + ratio * 9)
            b = int(21 + ratio * 12)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Layout Geometry
        chart_top = 105
        chart_bottom = height - 55
        chart_left = 50
        chart_right = width - 110
        chart_h = chart_bottom - chart_top
        chart_w = chart_right - chart_left

        # Last 24-28 candles
        display_candles = candles[-26:] if len(candles) >= 26 else candles
        if not display_candles:
            display_candles = [
                Candle(timestamp=int(datetime.now().timestamp()), open=1.0850, high=1.0855, low=1.0848, close=1.0852, volume=100.0)
            ]

        num_candles = len(display_candles)

        # Price scale calculation
        min_p = min(c.low for c in display_candles)
        max_p = max(c.high for c in display_candles)

        ref_price = signal_data.get("reference_price", display_candles[-1].close)
        sup_val = signal_data.get("support_level")
        res_val = signal_data.get("resistance_level")

        all_p = [min_p, max_p, float(ref_price)]
        if sup_val:
            all_p.append(float(sup_val))
        if res_val:
            all_p.append(float(res_val))

        min_p = min(all_p)
        max_p = max(all_p)

        padding = max((max_p - min_p) * 0.22, 0.00025)
        y_min = min_p - padding
        y_max = max_p + padding
        p_range = max(y_max - y_min, 0.00001)

        def price_to_y(p: float) -> int:
            norm = (p - y_min) / p_range
            return int(chart_bottom - (norm * chart_h))

        # 1. Grid Lines & Right Price Scale
        grid_count = 6
        for i in range(grid_count + 1):
            p_val = y_min + (i * (p_range / grid_count))
            y_pos = price_to_y(p_val)
            # Grid Line
            draw.line([(chart_left, y_pos), (chart_right, y_pos)], fill=(22, 30, 44), width=1)
            # Right Y-Axis Label
            draw.text((chart_right + 12, y_pos - 9), f"{p_val:.5f}", fill=(140, 160, 185), font=font_axis)

        # 2. SMC 10 Moving Average Line (Glowing Amber)
        if len(candles) >= 5:
            closes = [c.close for c in candles]
            smc_points = []
            candle_step = chart_w / max(num_candles, 1)
            start_offset = len(candles) - num_candles

            for idx, c in enumerate(display_candles):
                c_idx = start_offset + idx
                if c_idx >= 9:
                    smc_val = sum(closes[c_idx - 9 : c_idx + 1]) / 10.0
                    cx = int(chart_left + (idx + 0.5) * candle_step)
                    cy = price_to_y(smc_val)
                    smc_points.append((cx, cy))

            if len(smc_points) >= 2:
                for j in range(len(smc_points) - 1):
                    # Glow effect
                    draw.line([smc_points[j], smc_points[j + 1]], fill=(255, 179, 0), width=3)

        # 3. Horizontal Support / Resistance Breakdown Level
        level_val = sup_val or res_val
        if level_val:
            ly = price_to_y(float(level_val))
            if chart_top <= ly <= chart_bottom:
                # Dashed Horizontal Line
                for dx in range(chart_left, chart_right, 16):
                    draw.line([(dx, ly), (min(dx + 9, chart_right), ly)], fill=(0, 229, 255), width=2)
                # Level Pill on Right Axis
                draw.rectangle([(chart_right + 8, ly - 12), (chart_right + 95, ly + 12)], fill=(0, 180, 216))
                draw.text((chart_right + 14, ly - 9), "KEY LEVEL", fill=(0, 0, 0), font=font_axis)

        # 4. Candlesticks
        candle_step = chart_w / max(num_candles, 1)
        body_w = max(int(candle_step * 0.70), 6)

        for i, c in enumerate(display_candles):
            cx = int(chart_left + (i + 0.5) * candle_step)
            is_bull = c.close >= c.open

            # Colors: Neon Green / Hot Red
            c_fill = (0, 230, 118) if is_bull else (255, 67, 112)
            c_wick = (0, 245, 130) if is_bull else (255, 80, 125)

            hy = price_to_y(c.high)
            ly = price_to_y(c.low)
            oy = price_to_y(c.open)
            cy = price_to_y(c.close)

            # Wicks
            draw.line([(cx, hy), (cx, ly)], fill=c_wick, width=2)

            # Candle Body
            top_y = min(oy, cy)
            bot_y = max(oy, cy)
            if bot_y - top_y < 3:
                bot_y = top_y + 3

            x1 = cx - body_w // 2
            x2 = cx + body_w // 2
            draw.rectangle([(x1, top_y), (x2, bot_y)], fill=c_fill, outline=c_wick)

            # Volume Bar at bottom
            vol_h = min(int((c.volume / 2500.0) * 40), 40)
            draw.rectangle([(x1, chart_bottom - vol_h), (x2, chart_bottom)], fill=(35, 48, 68))

        # 5. Entry Trigger Marker (Last Candle)
        trigger_cx = int(chart_left + (num_candles - 0.5) * candle_step)
        direction = signal_data.get("direction", "DOWN").upper()
        is_call = direction in ["UP", "LONG", "BUY", "CALL"]
        trigger_c = display_candles[-1]

        action_color = (0, 230, 118) if is_call else (255, 59, 48)
        action_text = "CALL (BUY) ⬆️" if is_call else "PUT (SELL) ⬇️"

        if is_call:
            # Arrow pointing UP
            tip_y = price_to_y(trigger_c.low) + 14
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 14, tip_y + 22),
                (trigger_cx + 14, tip_y + 22)
            ], fill=action_color)
            # Floating Pill Badge
            box_top = tip_y + 26
            draw.rectangle([(trigger_cx - 95, box_top), (trigger_cx + 95, box_top + 34)], fill=action_color)
            draw.text((trigger_cx - 86, box_top + 6), f"{action_text} @ {ref_price:.5f}", fill=(0, 0, 0), font=font_entry)
        else:
            # Arrow pointing DOWN
            tip_y = price_to_y(trigger_c.high) - 14
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 14, tip_y - 22),
                (trigger_cx + 14, tip_y - 22)
            ], fill=action_color)
            # Floating Pill Badge
            box_top = tip_y - 62
            draw.rectangle([(trigger_cx - 95, box_top), (trigger_cx + 95, box_top + 34)], fill=action_color)
            draw.text((trigger_cx - 86, box_top + 6), f"{action_text} @ {ref_price:.5f}", fill=(255, 255, 255), font=font_entry)

        # 6. Header Styling
        asset = signal_data.get("asset_symbol", "EUR/USD (OTC)")
        pattern_name = signal_data.get("pattern_name", "Pattern Type 14")
        ai_score = signal_data.get("ai_score", 88)

        # Header Bar Background
        draw.rectangle([(0, 0), (width, 88)], fill=(15, 21, 33))
        draw.line([(0, 88), (width, 88)], fill=(32, 45, 65), width=2)

        # Logo Badge
        draw.rectangle([(25, 20), (210, 68)], fill=(0, 229, 255))
        draw.text((38, 30), "TRADEPULSE AI", fill=(0, 0, 0), font=font_logo)

        # Asset & Live Price
        draw.text((230, 26), f"{asset}", fill=(255, 255, 255), font=font_asset)
        draw.text((460, 32), "1M OTC", fill=(140, 160, 185), font=font_header_sub)
        draw.text((560, 28), f"Price: {ref_price:.5f}", fill=(0, 230, 118), font=font_asset)

        # Right Header Strategy Info & AI Score
        draw.text((width - 480, 18), f"Strategy: {pattern_name}", fill=(255, 215, 0), font=font_strategy)
        draw.rectangle([(width - 480, 48), (width - 150, 78)], fill=(0, 229, 255))
        draw.text((width - 470, 52), f"AI SCORE: {ai_score}% (HIGH ACCURACY)", fill=(0, 0, 0), font=font_badge)

        # 7. Legend & Footer Bar
        draw.rectangle([(0, height - 42), (width, height)], fill=(12, 16, 26))
        draw.line([(0, height - 42), (width, height - 42)], fill=(28, 38, 54), width=1)

        draw.text((25, height - 32), "🟡 SMC 10 Moving Average    🔵 Horizontal Breakdown / Support Level    🟢 CALL / 🔴 PUT Live Trade Setup", fill=(150, 170, 195), font=font_footer)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((width - 340, height - 32), f"Live Quotex Stream • {now_str}", fill=(120, 140, 165), font=font_footer)

        # Save Image
        img.save(output_path, "PNG", quality=95)
        return output_path
