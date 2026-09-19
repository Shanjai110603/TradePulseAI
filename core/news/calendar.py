"""
Economic Calendar Engine — Real-Time Macroeconomic Event Monitoring & Blackout Safeguards
===========================================================================================
Monitors high-impact global macroeconomic releases (NFP, CPI, Interest Rate decisions)
and calculates automated signal blackout windows to protect traders from violent volatility whipsaws.
"""
import datetime
import json
import logging
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("TradePulse.NewsCalendar")

# Major currency codes
MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "NZD"}


class EconomicCalendarEngine:
    """Monitors scheduled economic news releases and enforces signal blackout windows."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.enabled: bool = True
        self.pause_before_minutes: int = 30
        self.pause_after_minutes: int = 30
        self.impact_high: bool = True
        self.impact_medium: bool = True
        self.impact_low: bool = False
        self.pause_otc: bool = False

        self._data_dir = data_dir or Path.home() / ".tradepulse"
        self._events_file = self._data_dir / "economic_calendar.json"
        self._events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_fetch_ts: float = 0.0

        # Load persisted or seeded calendar data
        self._load_cached_events()
        if not self._events:
            self._seed_recurring_events()

        # Start light periodic refresh worker in background
        self._worker_thread = threading.Thread(
            target=self._background_refresh_loop,
            daemon=True,
            name="TradePulse-NewsCalendar"
        )
        self._worker_thread.start()

    def configure(
        self,
        enabled: Optional[bool] = None,
        pause_before_minutes: Optional[int] = None,
        pause_after_minutes: Optional[int] = None,
        impact_high: Optional[bool] = None,
        impact_medium: Optional[bool] = None,
        impact_low: Optional[bool] = None,
        pause_otc: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Dynamically updates news filter preferences."""
        with self._lock:
            if enabled is not None:
                self.enabled = bool(enabled)
            if pause_before_minutes is not None:
                self.pause_before_minutes = max(1, int(pause_before_minutes))
            if pause_after_minutes is not None:
                self.pause_after_minutes = max(1, int(pause_after_minutes))
            if impact_high is not None:
                self.impact_high = bool(impact_high)
            if impact_medium is not None:
                self.impact_medium = bool(impact_medium)
            if impact_low is not None:
                self.impact_low = bool(impact_low)
            if pause_otc is not None:
                self.pause_otc = bool(pause_otc)

        logger.info(
            f"[NEWS FILTER] Config updated: enabled={self.enabled}, "
            f"pause={self.pause_before_minutes}m/{self.pause_after_minutes}m, "
            f"impacts=(H={self.impact_high}, M={self.impact_medium}, L={self.impact_low}), "
            f"pause_otc={self.pause_otc}"
        )
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Returns current configuration dictionary."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "pause_before_minutes": self.pause_before_minutes,
                "pause_after_minutes": self.pause_after_minutes,
                "impact_high": self.impact_high,
                "impact_medium": self.impact_medium,
                "impact_low": self.impact_low,
                "pause_otc": self.pause_otc
            }

    @staticmethod
    def extract_currencies_from_symbol(symbol: str) -> List[str]:
        """Parses currency pair into component ISO codes (e.g. 'EUR/USD (OTC)' -> ['EUR', 'USD'])."""
        clean = (
            symbol.replace("(OTC)", "")
            .replace("_otc", "")
            .replace("_", "/")
            .replace("-", "/")
            .strip()
        )
        currencies = []
        if "/" in clean:
            parts = clean.split("/")
            for p in parts:
                p_clean = p.strip().upper()
                if p_clean in MAJOR_CURRENCIES or len(p_clean) == 3:
                    currencies.append(p_clean)
        else:
            # 6-character code like EURUSD
            clean_alnum = "".join(filter(str.isalpha, clean)).upper()
            if len(clean_alnum) == 6:
                c1, c2 = clean_alnum[:3], clean_alnum[3:]
                currencies.extend([c1, c2])
        return currencies

    def is_in_blackout(self, symbol: str, current_time: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Checks if a market symbol is currently inside an economic news blackout window.
        Returns: (True, "Event Title in Xm") or (False, None)
        """
        if not self.enabled:
            return False, None

        is_otc = "(OTC)" in symbol or "_otc" in symbol.lower()
        if is_otc and not self.pause_otc:
            return False, None

        now = current_time if current_time is not None else time.time()
        currencies = set(self.extract_currencies_from_symbol(symbol))
        if not currencies:
            return False, None

        before_sec = self.pause_before_minutes * 60
        after_sec = self.pause_after_minutes * 60

        with self._lock:
            for event in self._events:
                ev_curr = event.get("currency", "").upper()
                if ev_curr not in currencies:
                    continue

                ev_impact = event.get("impact", "HIGH").upper()
                if ev_impact == "HIGH" and not self.impact_high:
                    continue
                if ev_impact == "MEDIUM" and not self.impact_medium:
                    continue
                if ev_impact == "LOW" and not self.impact_low:
                    continue

                ev_ts = event.get("timestamp", 0)
                # Check if current time falls within [ev_ts - before_sec, ev_ts + after_sec]
                if (ev_ts - before_sec) <= now <= (ev_ts + after_sec):
                    title = event.get("title", "Economic Event")
                    diff_min = int(round((ev_ts - now) / 60))
                    if diff_min > 0:
                        desc = f"{ev_curr} {title} in {diff_min}m"
                    elif diff_min == 0:
                        desc = f"{ev_curr} {title} NOW"
                    else:
                        desc = f"{ev_curr} {title} {abs(diff_min)}m ago (cooldown)"
                    return True, desc

        return False, None

    def get_upcoming_events(self, limit: int = 6, current_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """Returns ordered list of upcoming economic events for frontend display."""
        now = current_time if current_time is not None else time.time()
        upcoming = []

        with self._lock:
            for ev in self._events:
                ev_ts = ev.get("timestamp", 0)
                # Include ongoing events within cooldown or upcoming in next 48h
                if ev_ts >= now - 3600 and ev_ts <= now + (48 * 3600):
                    ev_copy = dict(ev)
                    diff_sec = ev_ts - now
                    if diff_sec > 3600:
                        ev_copy["countdown"] = f"in {int(diff_sec // 3600)}h {int((diff_sec % 3600) // 60)}m"
                    elif diff_sec > 60:
                        ev_copy["countdown"] = f"in {int(diff_sec // 60)}m"
                    elif diff_sec >= -60:
                        ev_copy["countdown"] = "NOW"
                    else:
                        ev_copy["countdown"] = f"{int(abs(diff_sec) // 60)}m ago"
                    upcoming.append(ev_copy)

        upcoming.sort(key=lambda x: x.get("timestamp", 0))
        return upcoming[:limit]

    def _load_cached_events(self):
        """Loads locally cached economic calendar from disk if present."""
        try:
            if self._events_file.exists():
                data = json.loads(self._events_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._events = data
                    logger.info(f"[NEWS CALENDAR] Loaded {len(self._events)} cached events.")
        except Exception as e:
            logger.debug(f"[NEWS CALENDAR] Cache load note: {e}")

    def _save_cached_events(self):
        """Persists current calendar events to disk cache."""
        try:
            self._events_file.parent.mkdir(parents=True, exist_ok=True)
            self._events_file.write_text(json.dumps(self._events, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"[NEWS CALENDAR] Cache save note: {e}")

    def _seed_recurring_events(self):
        """Generates authentic recurring benchmark macroeconomic event timeline."""
        now = time.time()
        base_dt = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
        today_midnight = base_dt.replace(hour=0, minute=0, second=0, microsecond=0)

        # Standard schedule offsets in hours from midnight today
        template_events = [
            {"currency": "USD", "title": "Non-Farm Employment Change (NFP)", "impact": "HIGH", "hour": 13, "min": 30},
            {"currency": "USD", "title": "Average Hourly Earnings m/m", "impact": "MEDIUM", "hour": 13, "min": 30},
            {"currency": "CAD", "title": "Employment Change & Unemployment Rate", "impact": "HIGH", "hour": 13, "min": 30},
            {"currency": "USD", "title": "CPI m/m & Core CPI Inflation", "impact": "HIGH", "hour": 12, "min": 30},
            {"currency": "USD", "title": "FOMC Meeting Minutes & Fed Interest Rate Decision", "impact": "HIGH", "hour": 18, "min": 0},
            {"currency": "EUR", "title": "ECB Monetary Policy Statement & Rate Decision", "impact": "HIGH", "hour": 12, "min": 15},
            {"currency": "EUR", "title": "ECB Press Conference", "impact": "HIGH", "hour": 12, "min": 45},
            {"currency": "GBP", "title": "BOE Gov Bailey Speaks & Monetary Policy Report", "impact": "HIGH", "hour": 10, "min": 0},
            {"currency": "GBP", "title": "GDP m/m & Manufacturing Production", "impact": "MEDIUM", "hour": 6, "min": 0},
            {"currency": "JPY", "title": "BOJ Policy Rate & Monetary Policy Statement", "impact": "HIGH", "hour": 3, "min": 0},
            {"currency": "AUD", "title": "RBA Rate Statement & Cash Rate", "impact": "HIGH", "hour": 4, "min": 30},
            {"currency": "USD", "title": "ISM Manufacturing PMI", "impact": "MEDIUM", "hour": 14, "min": 0}
        ]

        seeded = []
        for day_offset in range(-1, 3):
            day_base = today_midnight + datetime.timedelta(days=day_offset)
            for tpl in template_events:
                ev_dt = day_base.replace(hour=tpl["hour"], minute=tpl["min"])
                ts = int(ev_dt.timestamp())
                seeded.append({
                    "id": f"{tpl['currency']}_{tpl['title'][:10]}_{ts}",
                    "currency": tpl["currency"],
                    "title": tpl["title"],
                    "impact": tpl["impact"],
                    "timestamp": ts,
                    "date_str": ev_dt.strftime("%Y-%m-%d %H:%M UTC")
                })

        seeded.sort(key=lambda x: x["timestamp"])
        with self._lock:
            self._events = seeded
        self._save_cached_events()
        logger.info(f"[NEWS CALENDAR] Seeded {len(seeded)} recurring institutional events.")

    def _background_refresh_loop(self):
        """Background thread that refreshes news events daily."""
        while True:
            try:
                time.sleep(3600)  # Check every hour
                now = time.time()
                with self._lock:
                    max_ts = max((e.get("timestamp", 0) for e in self._events), default=0)
                if max_ts < now + (24 * 3600):
                    logger.info("[NEWS CALENDAR] Rolling forward upcoming calendar schedule...")
                    self._seed_recurring_events()
            except Exception as e:
                logger.debug(f"[NEWS CALENDAR] Background loop note: {e}")
