"""
Shared Quotex Socket.IO Frame Parser
=====================================
Quotex's frontend talks to its backend over a socket.io (Engine.IO) websocket.
Every real message that matters for candles/ticks arrives as a text frame
shaped like:  42["event/name", {...payload...}]

This parser is intentionally shared by:
  - QuotexWebSocketClient (our own direct, hand-rolled connection attempt)
  - quotex_browser_relay.py (a real logged-in browser sniffing its own traffic)

Sniffing frames from a real, already-authenticated browser session (the relay)
is far more reliable than replaying our own guessed auth handshake, because
Quotex owns and controls that handshake and can change it at any time without
notice. Keeping the parsing logic here means both paths benefit from fixes.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Event name fragments that carry candle/history data
CANDLE_EVENT_HINTS = ("history", "candle", "instruments/update")
# Event name fragments that carry a single live tick
TICK_EVENT_HINTS = ("tick", "quote")


def parse_socketio_frame(raw: str) -> Optional[Tuple[str, Any]]:
    """
    Decodes a raw Engine.IO/Socket.IO text frame.
    Returns (event_name, payload) for message frames ("42[...]"), or:
      - ("__ping__", None) for a bare ping frame ("2") that needs a pong reply
      - ("__reject__", None) if the frame indicates the session was rejected
      - None if the frame isn't a data frame we care about (handshake noise, etc.)
    """
    if raw is None:
        return None
    if raw == "2":
        return ("__ping__", None)
    if not raw.startswith("42"):
        return None

    try:
        data = json.loads(raw[2:])
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, list) or not data:
        return None

    event = str(data[0])
    if "authorization/reject" in event or "unauthorized" in event.lower():
        return ("__reject__", None)

    payload = data[1] if len(data) > 1 else None
    return (event, payload)


def extract_candles_from_payload(event: str, payload: Any) -> List[Dict[str, float]]:
    """
    Given a decoded (event, payload) pair, extracts a list of
    {time, open, high, low, close} dicts if this event carries candle data.
    Returns an empty list if this event/payload isn't candle data.
    """
    if not any(hint in event for hint in CANDLE_EVENT_HINTS):
        return []

    candles_raw: List[Any] = []
    if isinstance(payload, dict):
        candles_raw = payload.get("candles", payload.get("data", payload.get("history", [])))
    elif isinstance(payload, list):
        candles_raw = payload

    out: List[Dict[str, float]] = []
    for c in candles_raw:
        try:
            if isinstance(c, (list, tuple)) and len(c) >= 5:
                out.append({
                    "time": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                })
            elif isinstance(c, dict) and ("time" in c or "t" in c):
                out.append({
                    "time": int(c.get("time", c.get("t", 0))),
                    "open": float(c.get("open", c.get("o", 0))),
                    "close": float(c.get("close", c.get("c", 0))),
                    "high": float(c.get("high", c.get("h", c.get("max", 0)))),
                    "low": float(c.get("low", c.get("l", c.get("min", 0)))),
                })
        except (TypeError, ValueError):
            continue
    return out


def extract_tick_from_payload(event: str, payload: Any) -> Optional[Dict[str, Any]]:
    """Given a decoded (event, payload) pair, extracts {asset, price, time} if this is a tick."""
    if not any(hint in event for hint in TICK_EVENT_HINTS):
        return None
    if not isinstance(payload, dict):
        # Quotex sometimes sends ticks as [asset, price, time] lists too
        if isinstance(payload, (list, tuple)) and len(payload) >= 2:
            try:
                return {"asset": str(payload[0]), "price": float(payload[1]),
                        "time": int(payload[2]) if len(payload) > 2 else None}
            except (TypeError, ValueError):
                return None
        return None
    try:
        price = payload.get("price", payload.get("p"))
        if price is None:
            return None
        return {
            "asset": payload.get("asset", payload.get("symbol")),
            "price": float(price),
            "time": payload.get("time", payload.get("t")),
        }
    except (TypeError, ValueError):
        return None
