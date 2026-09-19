"""
Trading Hours & Session Schedule Filter
=======================================
Enforces user-configured trading schedules, allowed active days of the week,
and operating session windows (e.g., London / NY overlap) with automatic standby.
"""
import datetime
import logging
import threading
import time
from typing import Dict, Any, List, Set, Optional, Tuple

logger = logging.getLogger("TradePulse.SessionScheduler")

WEEKDAY_MAP = {
    0: "Mo",
    1: "Tu",
    2: "We",
    3: "Th",
    4: "Fr",
    5: "Sa",
    6: "Su"
}


class SessionScheduler:
    """Manages active trading schedules and evaluates whether market hours are active."""

    def __init__(self):
        self.enabled: bool = False  # Disabled by default so 24/7 OTC works out of the box
        self.allowed_days: Set[str] = {"Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"}
        self.start_time: str = "00:00"
        self.end_time: str = "23:59"
        self.use_utc: bool = True
        self._lock = threading.Lock()

    def configure(
        self,
        enabled: Optional[bool] = None,
        allowed_days: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        use_utc: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Dynamically updates trading schedule preferences."""
        with self._lock:
            if enabled is not None:
                self.enabled = bool(enabled)
            if allowed_days is not None:
                valid = {"Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"}
                cleaned = {d.strip().capitalize()[:2] for d in allowed_days if d.strip().capitalize()[:2] in valid}
                if cleaned:
                    self.allowed_days = cleaned
            if start_time is not None and self._validate_time_str(start_time):
                self.start_time = start_time.strip()
            if end_time is not None and self._validate_time_str(end_time):
                self.end_time = end_time.strip()
            if use_utc is not None:
                self.use_utc = bool(use_utc)

        logger.info(
            f"[SESSION SCHEDULER] Config updated: enabled={self.enabled}, "
            f"days={sorted(list(self.allowed_days))}, window={self.start_time}-{self.end_time}, "
            f"use_utc={self.use_utc}"
        )
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Returns current configuration dictionary."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "allowed_days": sorted(list(self.allowed_days)),
                "start_time": self.start_time,
                "end_time": self.end_time,
                "use_utc": self.use_utc
            }

    @staticmethod
    def _validate_time_str(t: str) -> bool:
        """Validates HH:MM format."""
        try:
            parts = t.strip().split(":")
            if len(parts) != 2:
                return False
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            return False

    def is_session_active(self, current_time: Optional[float] = None) -> Tuple[bool, str]:
        """
        Evaluates whether current moment is within user-configured trading schedule.
        Returns: (is_active: bool, description: str)
        """
        if not self.enabled:
            return True, "Trading schedule filter disabled (24/7 active)"

        now_ts = current_time if current_time is not None else time.time()
        with self._lock:
            if self.use_utc:
                dt = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone.utc)
            else:
                dt = datetime.datetime.fromtimestamp(now_ts)

            # 1. Day of Week Check
            day_code = WEEKDAY_MAP.get(dt.weekday(), "Mo")
            if day_code not in self.allowed_days:
                return False, f"Trading paused on {day_code} (not in scheduled days: {', '.join(sorted(self.allowed_days))})"

            # 2. Operating Time Window Check
            try:
                start_h, start_m = map(int, self.start_time.split(":"))
                end_h, end_m = map(int, self.end_time.split(":"))
                now_mins = dt.hour * 60 + dt.minute
                start_mins = start_h * 60 + start_m
                end_mins = end_h * 60 + end_m

                if start_mins <= end_mins:
                    # Normal intraday window (e.g. 09:00 -> 21:00)
                    is_in_window = start_mins <= now_mins <= end_mins
                else:
                    # Overnight wrap-around window (e.g. 22:00 -> 06:00)
                    is_in_window = now_mins >= start_mins or now_mins <= end_mins

                if not is_in_window:
                    tz_label = "UTC" if self.use_utc else "Local"
                    return False, f"Outside scheduled window ({self.start_time} - {self.end_time} {tz_label})"

            except Exception as e:
                logger.debug(f"[SESSION SCHEDULER] Time parse note: {e}")
                return True, "Active (parse fallback)"

            return True, "Session Active"
