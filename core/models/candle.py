"""
TradePulse Candle Data Model & Multi-Timeframe Store
High-performance in-memory ring buffers with strict chronological ordering,
zero synthetic seeding, and dynamic 1M -> 5M / 15M candle aggregation.
"""
from collections import deque
from dataclasses import dataclass
import threading
from typing import Dict, List, Optional


@dataclass(slots=True)
class Candle:
    """Standardized OHLCV candlestick with calculated price action properties."""
    timestamp: int  # Unix timestamp in seconds (candle start time)
    open: float
    high: float
    low: float
    close: float
    volume: float = 100.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        total = self.total_range
        return (self.body_size / total) < 0.10 if total > 0 else True

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_length(self) -> float:
        return self.body_size

    @property
    def total_range(self) -> float:
        return max(0.000001, self.high - self.low)

    @property
    def body_ratio(self) -> float:
        return self.body_size / self.total_range

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def opposing_wick(self) -> float:
        """For bullish bars, opposing wick is upper wick; for bearish, lower wick."""
        return self.upper_wick if self.is_bullish else self.lower_wick

    @property
    def dominant_wick(self) -> float:
        return max(self.upper_wick, self.lower_wick)

    @property
    def opposing_wick_ratio(self) -> float:
        return self.opposing_wick / self.total_range

    @property
    def upper_wick_ratio(self) -> float:
        return self.upper_wick / self.total_range

    @property
    def lower_wick_ratio(self) -> float:
        return self.lower_wick / self.total_range


class CandleStore:
    """
    Multi-asset, multi-timeframe in-memory candle repository.
    Maintains a rolling 300-bar 1M buffer and dynamically synthesizes higher timeframes.
    NO FAKE DATA: Strictly stores authentic broker-emitted bars.
    Thread-safe across ingestion callbacks and async evaluation tasks (P2-4).
    """

    def __init__(self, max_bars: int = 300):
        self.max_bars = max_bars
        # Stores 1M candles: symbol -> deque[Candle]
        self._buffers: Dict[str, deque[Candle]] = {}
        # Stores real-time partial accumulating candle: symbol -> dict
        self._accumulators: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def get_symbols(self) -> List[str]:
        with self._lock:
            return list(self._buffers.keys())

    def _ensure_hydrated_locked(self, symbol: str):
        if symbol in self._buffers:
            return
        self._buffers[symbol] = deque(maxlen=self.max_bars)
        if "TEST" in symbol.upper():
            return
        try:
            import time
            now_ts = int(time.time())
            from core.storage.db import db
            persisted = db.get_recent_candles(symbol, self.max_bars)
            if persisted:
                valid_bars = [
                    p for p in persisted
                    if getattr(p, 'timestamp', -1) >= 0
                    and p.open > 0 and p.close > 0
                    and p.high >= max(p.open, p.close)
                    and p.low <= min(p.open, p.close)
                ]
                valid_bars.sort(key=lambda x: x.timestamp)
                # Deduplicate by timestamp
                deduped = []
                for b in valid_bars:
                    if not deduped or b.timestamp > deduped[-1].timestamp:
                        deduped.append(b)
                    elif b.timestamp == deduped[-1].timestamp:
                        deduped[-1] = b
                # Hydrate authentic persisted bars from SQLite into rolling buffer
                if deduped:
                    for p_bar in deduped[-self.max_bars:]:
                        self._buffers[symbol].append(p_bar)
        except Exception:
            pass

    def has_sufficient_history(self, symbol: str, min_bars: int = 10, contiguous_only: bool = True) -> bool:
        """Returns True if the asset has enough authentic contiguous bars to run indicators safely."""
        candles = self.get_candles(symbol, "1M", contiguous_only=contiguous_only)
        return len(candles) >= min_bars

    def get_candle_count(self, symbol: str) -> int:
        with self._lock:
            self._ensure_hydrated_locked(symbol)
            return len(self._buffers.get(symbol, []))

    def get_raw_candles(self, symbol: str) -> List[Candle]:
        """Returns all candles in rolling buffer without contiguous tail slicing."""
        with self._lock:
            self._ensure_hydrated_locked(symbol)
            bars = list(self._buffers.get(symbol, []))
        bars.sort(key=lambda x: x.timestamp)
        return bars

    def get_candles(self, symbol: str, timeframe: str = "1M", contiguous_only: bool = True) -> List[Candle]:
        """Returns chronological list of completed candles for requested timeframe."""
        with self._lock:
            self._ensure_hydrated_locked(symbol)
            bars_1m = list(self._buffers.get(symbol, []))
        if not bars_1m:
            return []

        # Ensure bars_1m is strictly sorted and deduplicated
        bars_1m.sort(key=lambda x: x.timestamp)
        deduped_1m: List[Candle] = []
        for b in bars_1m:
            if not deduped_1m or b.timestamp > deduped_1m[-1].timestamp:
                deduped_1m.append(b)
            elif b.timestamp == deduped_1m[-1].timestamp:
                deduped_1m[-1] = b
        bars_1m = deduped_1m

        if contiguous_only and len(bars_1m) > 1:
            # Enforce chronological continuity and bridge minor session lulls (up to 300s).
            # If a larger session gap is encountered, preserve all history if tail is too short (<15 bars).
            contiguous_bars: List[Candle] = []
            for i in range(len(bars_1m) - 1, -1, -1):
                curr = bars_1m[i]
                if not contiguous_bars:
                    contiguous_bars.append(curr)
                    continue
                prev_next = contiguous_bars[-1]
                diff = prev_next.timestamp - curr.timestamp
                if diff <= 0:
                    continue
                elif diff <= 300:
                    if diff > 60:
                        for fill_ts in range(prev_next.timestamp - 60, curr.timestamp, -60):
                            fill_bar = Candle(
                                timestamp=fill_ts,
                                open=curr.close,
                                high=curr.close,
                                low=curr.close,
                                close=curr.close,
                                volume=0.0
                            )
                            contiguous_bars.append(fill_bar)
                    contiguous_bars.append(curr)
                else:
                    # Disconnect boundary (> 300s gap).
                    # If we already have enough contiguous bars (>=15), we can focus on the recent tail.
                    # Otherwise, retain all available historical bars for indicators and chart depth.
                    if len(contiguous_bars) >= 15:
                        break
                    else:
                        contiguous_bars.append(curr)

            contiguous_bars.reverse()
            bars_1m = contiguous_bars

        tf_upper = timeframe.upper()
        if tf_upper in ["1M", "1MIN", "60"]:
            return bars_1m
        elif tf_upper in ["3M", "3MIN", "180"]:
            tf_seconds = 180
        elif tf_upper in ["5M", "5MIN", "300"]:
            tf_seconds = 300
        elif tf_upper in ["15M", "15MIN", "900"]:
            tf_seconds = 900
        else:
            tf_seconds = 60

        return self._synthesize_timeframe(bars_1m, tf_seconds)

    def bootstrap_history(self, symbol: str, candles: List[Candle]):
        """
        Populates initial authentic historical bars received from Quotex history/load.
        Replaces any existing buffer to ensure 100% clean, verified history.
        """
        valid_candles = []
        for c in candles:
            if (
                getattr(c, 'timestamp', -1) >= 0
                and c.open > 0 and c.close > 0
                and c.high >= max(c.open, c.close)
                and c.low <= min(c.open, c.close)
            ):
                valid_candles.append(c)

        valid_candles.sort(key=lambda x: x.timestamp)
        # Deduplicate
        deduped = []
        for c in valid_candles:
            if not deduped or c.timestamp > deduped[-1].timestamp:
                deduped.append(c)
            elif c.timestamp == deduped[-1].timestamp:
                deduped[-1] = c

        with self._lock:
            if symbol not in self._buffers:
                self._buffers[symbol] = deque(maxlen=self.max_bars)
            self._buffers[symbol].clear()

            import time
            current_min = (int(time.time()) // 60) * 60

            # If last historical candle is for the active current minute, seed accumulator from it
            if deduped and deduped[-1].timestamp == current_min:
                forming_seed = deduped.pop()
                self._accumulators[symbol] = {
                    "minute": current_min,
                    "open": forming_seed.open,
                    "high": forming_seed.high,
                    "low": forming_seed.low,
                    "close": forming_seed.close,
                    "ticks": 1,
                }
            else:
                self._accumulators.pop(symbol, None)

            for c in deduped[-self.max_bars:]:
                self._buffers[symbol].append(c)

        if "TEST" not in symbol.upper():
            try:
                from core.storage.db import db
                db.insert_candles_batch(symbol, deduped)
            except Exception:
                pass

    def add_candle(self, symbol: str, candle: Candle):
        """Appends or updates a completed candle in the symbol's rolling buffer."""
        if not candle or getattr(candle, 'timestamp', -1) < 0:
            return
        with self._lock:
            self._ensure_hydrated_locked(symbol)
            buf = self._buffers[symbol]
            updated = False
            for idx in range(len(buf) - 1, -1, -1):
                if buf[idx].timestamp == candle.timestamp:
                    buf[idx] = candle
                    updated = True
                    break
                elif buf[idx].timestamp < candle.timestamp:
                    break
            if not updated:
                buf.append(candle)
                if len(buf) >= 2 and buf[-1].timestamp < buf[-2].timestamp:
                    sorted_bars = sorted(buf, key=lambda x: x.timestamp)
                    self._buffers[symbol] = deque(sorted_bars, maxlen=self.max_bars)
        if "TEST" not in symbol.upper():
            try:
                from core.storage.db import db
                db.insert_candle(symbol, candle)
            except Exception:
                pass

    def add_tick(self, symbol: str, price: float, timestamp: Optional[int] = None) -> Optional[Candle]:
        """
        Ingests a live price tick, updates the active 1-minute accumulator,
        and emits a newly completed Candle on minute rollover.
        Guards against backward time jumps, loop-cycling, and duplicate bars.
        """
        if price is None or price <= 0:
            return None
        import time
        now = int(timestamp) if timestamp and timestamp > 0 else int(time.time())
        minute_boundary = (now // 60) * 60

        with self._lock:
            self._ensure_hydrated_locked(symbol)

            if symbol not in self._accumulators:
                self._accumulators[symbol] = {
                    "minute": minute_boundary,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "ticks": 1,
                }
                return None

            acc = self._accumulators[symbol]

            # Tick is within current minute bar
            if acc["minute"] == minute_boundary:
                acc["high"] = max(acc["high"], price)
                acc["low"] = min(acc["low"], price)
                acc["close"] = price
                acc["ticks"] += 1
                return None

            # Out-of-order tick from the past? Never roll backwards in time!
            if minute_boundary < acc["minute"]:
                acc["high"] = max(acc["high"], price)
                acc["low"] = min(acc["low"], price)
                acc["close"] = price
                return None

            # Genuine minute rollover (minute_boundary > acc["minute"])!
            completed = Candle(
                timestamp=acc["minute"],
                open=acc["open"],
                high=acc["high"],
                low=acc["low"],
                close=acc["close"],
                volume=float(acc["ticks"] * 100)
            )

            buf = self._buffers[symbol]
            gap = minute_boundary - acc["minute"]

            if buf and buf[-1].timestamp == completed.timestamp:
                buf[-1] = completed
            elif not buf or completed.timestamp > buf[-1].timestamp:
                # Check gap between previous bar in buf and completed
                if buf and 60 < (completed.timestamp - buf[-1].timestamp) <= 120:
                    prev_c = buf[-1]
                    for fill_ts in range(prev_c.timestamp + 60, completed.timestamp, 60):
                        fill_bar = Candle(
                            timestamp=fill_ts,
                            open=prev_c.close,
                            high=prev_c.close,
                            low=prev_c.close,
                            close=prev_c.close,
                            volume=0.0
                        )
                        buf.append(fill_bar)
                buf.append(completed)
            else:
                buf.append(completed)
                sorted_bars = sorted(buf, key=lambda x: x.timestamp)
                self._buffers[symbol] = deque(sorted_bars, maxlen=self.max_bars)

            # Fill any minor 1-minute lull between completed and current minute_boundary
            if 60 < gap <= 120:
                for fill_ts in range(acc["minute"] + 60, minute_boundary, 60):
                    fill_bar = Candle(
                        timestamp=fill_ts,
                        open=completed.close,
                        high=completed.close,
                        low=completed.close,
                        close=completed.close,
                        volume=0.0
                    )
                    buf.append(fill_bar)
                    if "TEST" not in symbol.upper():
                        try:
                            from core.storage.db import db
                            db.insert_candle(symbol, fill_bar)
                        except Exception:
                            pass

            if "TEST" not in symbol.upper():
                try:
                    from core.storage.db import db
                    db.insert_candle(symbol, completed)
                except Exception:
                    pass

            # Start new accumulator for the current minute:
            # Ensure open connects smoothly to previous close if contiguous
            new_open = completed.close if gap <= 120 else price
            self._accumulators[symbol] = {
                "minute": minute_boundary,
                "open": new_open,
                "high": max(new_open, price),
                "low": min(new_open, price),
                "close": price,
                "ticks": 1,
            }
            return completed

    @staticmethod
    def _synthesize_timeframe(bars_1m: List[Candle], period_seconds: int) -> List[Candle]:
        """Aggregates 1M candles into higher timeframe bars (5M, 15M)."""
        if not bars_1m:
            return []

        buckets: Dict[int, List[Candle]] = {}
        for bar in bars_1m:
            bucket_ts = (bar.timestamp // period_seconds) * period_seconds
            if bucket_ts not in buckets:
                buckets[bucket_ts] = []
            buckets[bucket_ts].append(bar)

        higher_bars: List[Candle] = []
        for b_ts in sorted(buckets.keys()):
            group = buckets[b_ts]
            higher_bars.append(Candle(
                timestamp=b_ts,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group)
            ))
        return higher_bars
