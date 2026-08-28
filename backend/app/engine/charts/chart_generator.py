import os
import math
import functools
from datetime import datetime, timezone, timedelta
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
    Renders authentic high-definition (1200x600) Quotex terminal-style candlestick charts
    matching the professional live platform: 45-50 continuous wave candles, Quotex neon
    emerald/coral colors, right-side price ladder, bottom time axis, and clean asset watermark.
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

        width = 1200
        height = 600
        asset = signal_data.get("asset_symbol", "EUR/USD (OTC)")
        direction = signal_data.get("direction", "DOWN").upper()
        is_call = direction in ["UP", "LONG", "BUY", "CALL"]
        payout = signal_data.get("payout_percent", 88)

        # Fonts
        font_watermark = _load_font(18, bold=True)
        font_axis = _load_font(14, bold=False)
        font_entry = _load_font(15, bold=True)

        # 1. Canvas with Quotex Deep Dark Platform Theme
        img = Image.new("RGB", (width, height), color=(12, 15, 22))
        draw = ImageDraw.Draw(img)

        # 2. Geometry
        chart_top = 45
        chart_bottom = height - 45
        chart_left = 35
        chart_right = width - 95
        chart_h = chart_bottom - chart_top
        chart_w = chart_right - chart_left

        # Show 45 to 50 continuous candles for natural wave progression (like Quotex desktop)
        if len(candles) >= 48:
            display_candles = candles[-48:]
        else:
            # Build continuous smooth pre-history wave if fewer candles are passed
            needed = 48 - len(candles)
            first_c = candles[0] if candles else Candle(timestamp=int(datetime.now().timestamp()), open=1.0850, high=1.0855, low=1.0848, close=1.0852, volume=100)
            synth_candles = []
            curr_p = first_c.open
            start_ts = first_c.timestamp - (needed * 60)
            step_vol = (first_c.high - first_c.low) * 0.4 or 0.00010
            for k in range(needed):
                # Gentle sine wave drift
                delta = math.sin(k * 0.35) * step_vol + ((k % 3 - 1) * step_vol * 0.5)
                op = curr_p
                cl = curr_p + delta
                hi = max(op, cl) + abs(delta * 0.6) + (step_vol * 0.2)
                lo = min(op, cl) - abs(delta * 0.6) - (step_vol * 0.2)
                synth_candles.append(Candle(timestamp=start_ts + (k * 60), open=op, high=hi, low=lo, close=cl, volume=1000 + (k % 5 * 200)))
                curr_p = cl
            display_candles = synth_candles + list(candles)

        num_candles = len(display_candles)
        ref_price = float(signal_data.get("reference_price", display_candles[-1].close))

        # 3. Dynamic Full-Canvas Auto-Fitting (Tight 8% margin for tall, rich candles)
        min_c = min(c.low for c in display_candles)
        max_c = max(c.high for c in display_candles)
        candle_span = max(max_c - min_c, 0.00008 if "JPY" not in asset else 0.015)

        pad = candle_span * 0.09
        y_min = min_c - pad
        y_max = max_c + pad
        p_range = max(y_max - y_min, 0.00001)

        def price_to_y(p: float) -> int:
            norm = (p - y_min) / p_range
            return int(chart_bottom - (norm * chart_h))

        # 4. Subtle Grid Lines (Quotex Matrix)
        grid_count = 6
        for i in range(grid_count + 1):
            p_val = y_min + (i * (p_range / grid_count))
            y_pos = price_to_y(p_val)
            # Horizontal line
            draw.line([(chart_left, y_pos), (chart_right, y_pos)], fill=(20, 25, 36), width=1)
            # Right Y-Axis Price Label
            draw.text((chart_right + 10, y_pos - 7), _format_price(p_val, asset), fill=(120, 138, 160), font=font_axis)

        # Vertical Grid Lines (every 6 candles)
        candle_step = chart_w / max(num_candles, 1)
        for i in range(0, num_candles, 6):
            cx = int(chart_left + (i + 0.5) * candle_step)
            draw.line([(cx, chart_top), (cx, chart_bottom)], fill=(18, 23, 33), width=1)

        # 5. Top-Left Quotex Terminal Watermark
        draw.text((chart_left + 10, 16), f"{asset} ({payout}%) | TF: M1", fill=(190, 205, 225), font=font_watermark)

        # 6. SMC 10 Line (Smooth Quotex Moving Average Ribbon)
        if len(display_candles) >= 5:
            closes = [c.close for c in display_candles]
            smc_points = []
            for idx in range(num_candles):
                lookback = min(idx + 1, 10)
                smc_val = sum(closes[idx - lookback + 1 : idx + 1]) / float(lookback)
                cx = int(chart_left + (idx + 0.5) * candle_step)
                cy = price_to_y(smc_val)
                smc_points.append((cx, cy))

            if len(smc_points) >= 2:
                for j in range(len(smc_points) - 1):
                    draw.line([smc_points[j], smc_points[j + 1]], fill=(255, 179, 0), width=2)

        # 7. Candlesticks (Quotex Neon Green / Coral Red)
        body_w = max(int(candle_step * 0.72), 8)

        for i, c in enumerate(display_candles):
            cx = int(chart_left + (i + 0.5) * candle_step)
            is_bull = c.close >= c.open

            # Quotex palette
            c_color = (0, 192, 118) if is_bull else (246, 70, 93)

            hy = price_to_y(c.high)
            ly = price_to_y(c.low)
            oy = price_to_y(c.open)
            cy = price_to_y(c.close)

            # Center Wick
            draw.line([(cx, hy), (cx, ly)], fill=c_color, width=2)

            # Solid Candle Body
            top_y = min(oy, cy)
            bot_y = max(oy, cy)
            if bot_y - top_y < 4:
                bot_y = top_y + 4

            x1 = cx - body_w // 2
            x2 = cx + body_w // 2
            draw.rectangle([(x1, top_y), (x2, bot_y)], fill=c_color)

            # Bottom X-Axis Time Labels (every 8th candle, in IST UTC+5:30)
            if i % 8 == 0 or i == num_candles - 1:
                try:
                    ist_tz = timezone(timedelta(hours=5, minutes=30))
                    c_dt = datetime.fromtimestamp(c.timestamp, tz=timezone.utc).astimezone(ist_tz)
                    t_str = c_dt.strftime("%H:%M")
                    draw.text((cx - 16, chart_bottom + 12), t_str, fill=(90, 110, 135), font=font_axis)
                except Exception:
                    pass

        # 8. Entry Trigger Arrow on Last Candle
        trigger_cx = int(chart_left + (num_candles - 0.5) * candle_step)
        trigger_c = display_candles[-1]
        action_color = (0, 215, 130) if is_call else (255, 60, 85)

        if is_call:
            # Green Arrow pointing UP below candle
            tip_y = price_to_y(trigger_c.low) + 12
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 10, tip_y + 14),
                (trigger_cx + 10, tip_y + 14)
            ], fill=action_color)
        else:
            # Red Arrow pointing DOWN above candle
            tip_y = price_to_y(trigger_c.high) - 12
            draw.polygon([
                (trigger_cx, tip_y),
                (trigger_cx - 10, tip_y - 14),
                (trigger_cx + 10, tip_y - 14)
            ], fill=action_color)

        # Save Image
        img.save(output_path, "PNG", quality=95)
        return output_path
