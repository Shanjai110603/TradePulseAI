import os
import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from app.engine.market_data.base import Candle


class TradeChartGenerator:
    """
    Generates a live, dark-themed candlestick chart of the actual trade setup.
    Renders actual candles, SMC 10 Line, Support/Resistance levels, and the Entry Trigger Arrow.
    """

    @classmethod
    def generate_chart(
        cls,
        candles: List[Candle],
        signal_data: Dict[str, Any],
        output_dir: str = "uploads/signals"
    ) -> str:
        """
        Renders a dark-mode candlestick chart of the trade and saves to PNG.
        Returns the absolute/relative filepath.
        """
        os.makedirs(output_dir, exist_ok=True)
        sig_id = signal_data.get("id", f"sig_{int(datetime.now().timestamp())}")
        output_path = os.path.join(output_dir, f"{sig_id}.png")

        width = 1100
        height = 620

        # Create canvas with rich dark gradient background
        img = Image.new("RGB", (width, height), color=(13, 17, 23))
        draw = ImageDraw.Draw(img)

        # Draw subtle background gradient/vignette
        for y in range(height):
            ratio = y / height
            r = int(10 + ratio * 6)
            g = int(14 + ratio * 8)
            b = int(22 + ratio * 10)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Chart Geometry
        chart_top = 85
        chart_bottom = height - 60
        chart_left = 65
        chart_right = width - 90
        chart_h = chart_bottom - chart_top
        chart_w = chart_right - chart_left

        # Slice last 25-30 candles
        display_candles = candles[-26:] if len(candles) >= 26 else candles
        if not display_candles:
            # Fallback dummy candle if none
            display_candles = [
                Candle(timestamp=int(datetime.now().timestamp()), open=1.0850, high=1.0855, low=1.0848, close=1.0852, volume=100.0)
            ]

        num_candles = len(display_candles)

        # Price bounds
        min_p = min(c.low for c in display_candles)
        max_p = max(c.high for c in display_candles)

        # Include support/resistance or SMC line in bounds if present
        ref_price = signal_data.get("reference_price", display_candles[-1].close)
        sup_res = signal_data.get("technical_snapshot", {}).get("support_levels", [])
        res_res = signal_data.get("technical_snapshot", {}).get("resistance_levels", [])
        
        all_levels = [min_p, max_p, ref_price]
        if sup_res:
            all_levels.extend(sup_res)
        if res_res:
            all_levels.extend(res_res)

        min_p = min(all_levels)
        max_p = max(all_levels)

        # Margin on price
        p_padding = max((max_p - min_p) * 0.18, 0.00020)
        y_min = min_p - p_padding
        y_max = max_p + p_padding
        p_range = max(y_max - y_min, 0.00001)

        def price_to_y(price: float) -> int:
            norm = (price - y_min) / p_range
            return int(chart_bottom - (norm * chart_h))

        # 1. Draw Grid Lines & Price Labels
        grid_steps = 6
        for i in range(grid_steps + 1):
            p_val = y_min + (i * (p_range / grid_steps))
            y_pos = price_to_y(p_val)
            # Grid line
            draw.line([(chart_left, y_pos), (chart_right, y_pos)], fill=(28, 36, 48), width=1)
            # Right Y-axis label
            draw.text((chart_right + 10, y_pos - 7), f"{p_val:.5f}", fill=(130, 145, 165))

        # 2. Draw SMC 10 Line / Moving Average
        if len(display_candles) >= 5:
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
                    draw.line([smc_points[j], smc_points[j + 1]], fill=(255, 179, 0), width=2)

        # 3. Draw Support / Resistance Level Line if applicable
        level_val = signal_data.get("support_level") or signal_data.get("resistance_level")
        if level_val:
            ly = price_to_y(float(level_val))
            if chart_top <= ly <= chart_bottom:
                # Dashed line
                for dx in range(chart_left, chart_right, 12):
                    draw.line([(dx, ly), (min(dx + 7, chart_right), ly)], fill=(0, 229, 255), width=2)
                # Badge on right
                draw.rectangle([(chart_right + 8, ly - 9), (chart_right + 78, ly + 9)], fill=(0, 180, 216))
                draw.text((chart_right + 12, ly - 6), "LEVEL", fill=(0, 0, 0))

        # 4. Draw Candlesticks
        candle_step = chart_w / max(num_candles, 1)
        candle_body_w = max(int(candle_step * 0.68), 4)

        for i, c in enumerate(display_candles):
            cx = int(chart_left + (i + 0.5) * candle_step)
            is_bull = c.close >= c.open

            c_color = (0, 230, 118) if is_bull else (255, 67, 112) # Neon Green / Crimson
            wick_color = (0, 200, 100) if is_bull else (230, 50, 90)

            high_y = price_to_y(c.high)
            low_y = price_to_y(c.low)
            open_y = price_to_y(c.open)
            close_y = price_to_y(c.close)

            # Upper & Lower Wicks
            draw.line([(cx, high_y), (cx, low_y)], fill=wick_color, width=2)

            # Body Box
            top_y = min(open_y, close_y)
            bot_y = max(open_y, close_y)
            if bot_y - top_y < 2:
                bot_y = top_y + 2

            x1 = cx - candle_body_w // 2
            x2 = cx + candle_body_w // 2
            draw.rectangle([(x1, top_y), (x2, bot_y)], fill=c_color, outline=wick_color)

            # Volume Bar at bottom
            vol_h = min(int((c.volume / 2000.0) * 35), 35)
            vol_y1 = chart_bottom - vol_h
            draw.rectangle([(x1, vol_y1), (x2, chart_bottom)], fill=(40, 55, 75, 120))

        # 5. Draw Entry Marker on Trigger Candle (Last Candle)
        trigger_cx = int(chart_left + (num_candles - 0.5) * candle_step)
        direction = signal_data.get("direction", "DOWN").upper()
        is_call = direction in ["UP", "LONG", "BUY", "CALL"]
        trigger_c = display_candles[-1]

        badge_color = (0, 230, 118) if is_call else (255, 59, 48)
        action_title = "CALL ⬆️" if is_call else "PUT ⬇️"

        if is_call:
            # Arrow pointing UP from below low
            arrow_tip_y = price_to_y(trigger_c.low) + 12
            draw.polygon([
                (trigger_cx, arrow_tip_y),
                (trigger_cx - 10, arrow_tip_y + 18),
                (trigger_cx + 10, arrow_tip_y + 18)
            ], fill=badge_color)
            # Entry badge box
            box_top = arrow_tip_y + 22
            draw.rectangle([(trigger_cx - 55, box_top), (trigger_cx + 55, box_top + 26)], fill=badge_color)
            draw.text((trigger_cx - 48, box_top + 5), f"{action_title} 1M", fill=(0, 0, 0))
        else:
            # Arrow pointing DOWN from above high
            arrow_tip_y = price_to_y(trigger_c.high) - 12
            draw.polygon([
                (trigger_cx, arrow_tip_y),
                (trigger_cx - 10, arrow_tip_y - 18),
                (trigger_cx + 10, arrow_tip_y - 18)
            ], fill=badge_color)
            # Entry badge box
            box_top = arrow_tip_y - 48
            draw.rectangle([(trigger_cx - 55, box_top), (trigger_cx + 55, box_top + 26)], fill=badge_color)
            draw.text((trigger_cx - 48, box_top + 5), f"{action_title} 1M", fill=(255, 255, 255))

        # 6. Header Styling
        asset = signal_data.get("asset_symbol", "EUR/USD (OTC)")
        pattern_name = signal_data.get("pattern_name", "Pattern Type 14")
        ai_score = signal_data.get("ai_score", 88)

        # Header background bar
        draw.rectangle([(0, 0), (width, 68)], fill=(18, 24, 38))
        draw.line([(0, 68), (width, 68)], fill=(35, 48, 68), width=2)

        # Top Badge
        draw.rectangle([(25, 16), (180, 52)], fill=(0, 229, 255))
        draw.text((38, 24), "TRADEPULSE AI", fill=(0, 0, 0))

        # Asset & Price
        draw.text((200, 22), f"{asset}", fill=(255, 255, 255))
        draw.text((390, 22), f"1M OTC", fill=(130, 150, 175))
        draw.text((480, 22), f"Price: {ref_price:.5f}", fill=(0, 230, 118))

        # Right Header Strategy Info
        draw.text((width - 430, 15), f"Strategy: {pattern_name}", fill=(255, 215, 0))
        draw.text((width - 430, 38), f"AI Confidence: {ai_score}% (HIGH)", fill=(0, 229, 255))

        # 7. Legend & Watermark Footer
        draw.line([(0, height - 32), (width, height - 32)], fill=(25, 35, 50), width=1)
        draw.text((25, height - 24), "🟡 SMC 10 Moving Average   🔵 Horizontal Breakout/Rejection Level", fill=(140, 155, 175))
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((width - 320, height - 24), f"Quotex OTC Live • {now_str}", fill=(110, 125, 145))

        # Save Image
        img.save(output_path, "PNG", quality=95)
        return output_path
