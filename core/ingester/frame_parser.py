"""
TradePulse Quotex Socket.IO Frame Parser
Decodes Engine.IO / Socket.IO text packets shaped like: 42["event", {...payload...}]
Extracts authentic historical candles, real-time ticks, and live payout percentages.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CANDLE_EVENT_HINTS = ("history", "candle", "instruments/update")
TICK_EVENT_HINTS = ("tick", "quote")


def parse_socketio_frame(raw: str) -> Optional[Tuple[str, Any]]:
    """
    Decodes an Engine.IO / Socket.IO frame.
    Returns:
      (event_name, payload) for "42[...]" message packets,
      ("__ping__", None) for ping "2" frames needing a pong reply,
      ("__reject__", None) if unauthorized,
      None for noise/handshakes.
    """
    if raw is None:
        return None
    if raw == "2":
        return ("__ping__", None)
    if not (raw.startswith("4") and "[" in raw):
        return None

    bracket_idx = raw.find("[")
    if bracket_idx == -1:
        return None

    try:
        data = json.loads(raw[bracket_idx:])
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, list) or not data:
        return None

    event = str(data[0])
    if "authorization/reject" in event or "unauthorized" in event.lower():
        return ("__reject__", None)

    payload = data[1] if len(data) > 1 else None
    return (event, payload)


def extract_candles_from_payload(event: str, payload: Any) -> Tuple[Optional[str], List[Dict[str, float]]]:
    """
    Extracts (asset_code, list of {time, open, close, high, low, volume}) from decoded payload.
    """
    if not any(hint in event for hint in CANDLE_EVENT_HINTS):
        return None, []

    asset_code: Optional[str] = None
    candles_raw: List[Any] = []

    if isinstance(payload, dict):
        asset_code = payload.get("asset") or payload.get("symbol")
        candles_raw = payload.get("candles") or payload.get("data") or payload.get("history") or []
    elif isinstance(payload, list):
        candles_raw = payload

    out: List[Dict[str, float]] = []

    # Detect if candles_raw is tick tuples [time, price] or [time, price, flag]
    if candles_raw and isinstance(candles_raw[0], (list, tuple)) and len(candles_raw[0]) in (2, 3):
        minute_bars: Dict[int, Dict[str, float]] = {}
        for c in candles_raw:
            try:
                t = int(float(c[0]))
                p = float(c[1])
                m_time = (t // 60) * 60
                if m_time not in minute_bars:
                    minute_bars[m_time] = {
                        "time": m_time,
                        "open": p,
                        "high": p,
                        "low": p,
                        "close": p,
                        "volume": 1.0
                    }
                else:
                    bar = minute_bars[m_time]
                    bar["close"] = p
                    if p > bar["high"]:
                        bar["high"] = p
                    if p < bar["low"]:
                        bar["low"] = p
                    bar["volume"] += 1.0
            except (TypeError, ValueError, IndexError):
                continue
        out = sorted(minute_bars.values(), key=lambda b: b["time"])
        return asset_code, out

    for c in candles_raw:
        try:
            # Array shape: [time, open, close, high, low]
            if isinstance(c, (list, tuple)) and len(c) >= 5:
                out.append({
                    "time": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                    "volume": float(c[5]) if len(c) > 5 else 100.0,
                })
            # Dict shape: {"time": ..., "open": ..., ...}
            elif isinstance(c, dict) and ("time" in c or "t" in c):
                out.append({
                    "time": int(c.get("time", c.get("t", 0))),
                    "open": float(c.get("open", c.get("o", 0.0))),
                    "close": float(c.get("close", c.get("c", 0.0))),
                    "high": float(c.get("high", c.get("h", c.get("max", 0.0)))),
                    "low": float(c.get("low", c.get("l", c.get("min", 0.0)))),
                    "volume": float(c.get("volume", c.get("v", 100.0))),
                })
        except (TypeError, ValueError):
            continue

    return asset_code, out


TICK_EVENT_HINTS = ("tick", "quote", "price", "live", "instruments/update", "1")


def _parse_single_tuple_tick(item: Any) -> Optional[Dict[str, Any]]:
    """
    Parses a single tick tuple, e.g. ['EURUSD_otc', 1699999999.123, 1.08452]
    or ['EURUSD_otc', 1.08452, 1699999999].
    Primary wire format is [asset, time, price].
    """
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    asset = str(item[0]).strip()
    if not asset or "," in asset or any(noise in asset.lower() for noise in ["put", "call", "bonus", "promo"]):
        return None
    # Real Quotex price ticks are always [asset, timestamp, price] or [asset, timestamp, price, volume] (len >= 3)
    # 2-element tuples like ['USDINR_otc', 86] represent payout or sentiment percentages, not price quotes
    if len(item) < 3:
        return None

    try:
        v1 = float(item[1])
        v2 = float(item[2])
        # Epoch timestamps in seconds (> 1_000_000) vs asset prices (< 1_000_000)
        if v1 > 1_000_000 and v2 <= 1_000_000:
            ts = v1 / 1000.0 if v1 > 100_000_000_000 else v1
            return {"asset": asset, "price": v2, "time": ts}
        elif v2 > 1_000_000 and v1 <= 1_000_000:
            ts = v2 / 1000.0 if v2 > 100_000_000_000 else v2
            return {"asset": asset, "price": v1, "time": ts}
        else:
            ts = v1 / 1000.0 if v1 > 100_000_000_000 else v1
            return {"asset": asset, "price": v2, "time": ts}
    except (TypeError, ValueError):
        return None


def extract_ticks_from_payload(event: str, payload: Any) -> List[Dict[str, Any]]:
    """
    Extracts a list of live ticks [{asset, price, time}, ...] from decoded payload.
    Correctly handles:
    1. Batched list of tick tuples: [["EURUSD_otc", 1699999999.123, 1.08452], ...]
    2. Single flat tuple: ["EURUSD_otc", 1699999999.123, 1.08452]
    3. Dict payload: {"asset": "EURUSD_otc", "price": 1.08452, "time": 1699999999}
    4. Candle history payload: extracts the latest closed bar as a live quote.
    """
    if not payload:
        return []

    ticks: List[Dict[str, Any]] = []

    # Case 1 & 2: List / Tuple payloads
    if isinstance(payload, (list, tuple)):
        if len(payload) == 0:
            return []

        # Check if it's a batch of items (list of lists/tuples)
        if isinstance(payload[0], (list, tuple)):
            for item in payload:
                parsed = _parse_single_tuple_tick(item)
                if parsed:
                    ticks.append(parsed)
            return ticks

        # Or a single flat tuple [asset, time, price] or [asset, price]
        if isinstance(payload[0], str):
            parsed = _parse_single_tuple_tick(payload)
            if parsed:
                ticks.append(parsed)
            return ticks

    # Case 3 & 4: Dict payload
    if isinstance(payload, dict):
        try:
            # Check for nested items list e.g. payload.data or payload.instruments
            nested_items = payload.get("data") or payload.get("instruments") or payload.get("rates")
            if isinstance(nested_items, list):
                for item in nested_items:
                    if isinstance(item, (list, tuple)):
                        parsed = _parse_single_tuple_tick(item)
                        if parsed:
                            ticks.append(parsed)
                    elif isinstance(item, dict):
                        a = item.get("asset") or item.get("symbol")
                        p = item.get("price") or item.get("close") or item.get("c") or item.get("rate")
                        if a and p is not None:
                            try:
                                ticks.append({"asset": a, "price": float(p), "time": item.get("time")})
                            except (TypeError, ValueError):
                                pass
                if ticks:
                    return ticks

            asset = payload.get("asset") or payload.get("symbol")
            price = payload.get("price") or payload.get("p") or payload.get("close") or payload.get("rate") or payload.get("c")
            if price is not None and asset:
                raw_time = payload.get("time", payload.get("t"))
                if raw_time is not None:
                    try:
                        raw_time = float(raw_time)
                        if raw_time > 100_000_000_000:
                            raw_time = raw_time / 1000.0
                    except (TypeError, ValueError):
                        pass
                ticks.append({
                    "asset": asset,
                    "price": float(price),
                    "time": raw_time,
                })
                return ticks

            # If candle array is present, extract the latest close price as an immediate quote
            candles = payload.get("candles") or payload.get("data") or payload.get("history")
            if asset and isinstance(candles, list) and len(candles) > 0:
                last_c = candles[-1]
                if isinstance(last_c, (list, tuple)):
                    if len(last_c) >= 5:
                        ticks.append({
                            "asset": asset,
                            "price": float(last_c[2]),  # close
                            "time": int(float(last_c[0])),
                        })
                        return ticks
                    elif len(last_c) >= 2:
                        ticks.append({
                            "asset": asset,
                            "price": float(last_c[1]),  # live tick price
                            "time": int(float(last_c[0])),
                        })
                        return ticks
                elif isinstance(last_c, dict) and ("close" in last_c or "c" in last_c):
                    ticks.append({
                        "asset": asset,
                        "price": float(last_c.get("close", last_c.get("c"))),
                        "time": int(last_c.get("time", last_c.get("t", 0))),
                    })
                    return ticks

            # Check if dict keys are asset names e.g. {"USDINR_otc": 83.925}
            for k, v in payload.items():
                if not isinstance(k, str) or len(k) < 3:
                    continue
                if k in ("time", "timestamp", "period", "count", "data", "instruments", "history", "candles"):
                    continue
                if "," in k or any(noise in k.lower() for noise in ["put", "call", "bonus", "promo", "profit", "payout"]):
                    continue
                if isinstance(v, (int, float)):
                    ticks.append({"asset": k, "price": float(v), "time": None})
                elif isinstance(v, (list, tuple)) and len(v) >= 1:
                    try:
                        if isinstance(v[0], (list, tuple)) and len(v[0]) >= 3:
                            last_bar = v[-1]
                            p = float(last_bar[2])
                            ticks.append({"asset": k, "price": p, "time": int(last_bar[0]) if len(last_bar) > 0 else None})
                        elif len(v) >= 2:
                            p = float(v[1] if float(v[0]) > 1_000_000 else v[0])
                            ticks.append({"asset": k, "price": p, "time": None})
                    except (TypeError, ValueError):
                        pass
                elif isinstance(v, dict):
                    p = v.get("price") or v.get("close") or v.get("c") or v.get("rate")
                    if p is not None:
                        try:
                            ticks.append({"asset": k, "price": float(p), "time": v.get("time")})
                        except (TypeError, ValueError):
                            pass
            if ticks:
                return ticks
        except (TypeError, ValueError):
            return []

    return ticks


def extract_tick_from_payload(event: str, payload: Any) -> Optional[Dict[str, Any]]:
    """
    Backwards-compatible wrapper returning the first extracted tick or None.
    """
    ticks = extract_ticks_from_payload(event, payload)
    return ticks[0] if ticks else None

