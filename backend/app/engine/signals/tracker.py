from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple


class SignalLifecycleTracker:
    """
    Tracks active research signals in real time.
    Calculates progress, price movement, target hits, expiry completions, and outcome determination.
    """

    @classmethod
    def evaluate_signal_tick(
        cls,
        signal_data: Dict[str, Any],
        current_price: float,
        current_time: Optional[datetime] = None
    ) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Evaluates current price against active signal.
        Returns:
            (new_status: str, is_completed: bool, event_details: dict)
        """
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        direction = signal_data.get("direction", "DOWN").upper()
        ref_price = signal_data.get("reference_price", 1.0)
        market_id = signal_data.get("market_id", "digital_options")
        raw_expiry = signal_data.get("expiry_time")
        if raw_expiry is not None:
            if isinstance(raw_expiry, str):
                try:
                    expiry_time = datetime.fromisoformat(raw_expiry)
                except Exception:
                    expiry_time = None
            else:
                expiry_time = raw_expiry

            if expiry_time and expiry_time.tzinfo is None:
                expiry_time = expiry_time.replace(tzinfo=timezone.utc)
        else:
            expiry_time = None

        current_status = signal_data.get("status", "ACTIVE")

        if current_status not in ["ACTIVE", "PENDING", "UPDATE"]:
            return current_status, True, {"reason": "Already resolved"}

        # Digital Options Style / Fixed Time Expiry resolution
        if market_id == "digital_options" or expiry_time:
            if expiry_time and now >= expiry_time:
                # Signal has reached expiry duration! Determine win/loss
                if direction in ["DOWN", "SHORT", "SELL"]:
                    outcome = "WIN" if current_price < ref_price else ("LOSS" if current_price > ref_price else "TIE")
                else:
                    outcome = "WIN" if current_price > ref_price else ("LOSS" if current_price < ref_price else "TIE")

                pnl_pct = ((ref_price - current_price) / ref_price * 100.0) if direction in ["DOWN", "SHORT", "SELL"] else ((current_price - ref_price) / ref_price * 100.0)
                return "EXPIRED", True, {
                    "outcome": outcome,
                    "exit_price": current_price,
                    "exit_time": now,
                    "pnl_percentage": round(pnl_pct, 4),
                    "reason": f"Expiry reached at {now.isoformat()} with price {current_price}"
                }

        # Standard Markets SL / TP Target resolution
        tp1 = signal_data.get("tp1")
        tp2 = signal_data.get("tp2")
        tp3 = signal_data.get("tp3")
        sl = signal_data.get("stop_loss")

        if direction in ["UP", "LONG", "BUY"]:
            if sl and current_price <= sl:
                return "COMPLETED", True, {
                    "outcome": "LOSS",
                    "exit_price": current_price,
                    "exit_time": now,
                    "reason": f"Stop Loss hit at {current_price:.5f}"
                }
            if tp3 and current_price >= tp3:
                return "COMPLETED", True, {
                    "outcome": "WIN",
                    "exit_price": current_price,
                    "exit_time": now,
                    "reason": f"TP3 Target reached at {current_price:.5f}"
                }
            if tp1 and current_price >= tp1 and current_status == "ACTIVE":
                return "UPDATE", False, {
                    "event": "TP1_REACHED",
                    "price": current_price,
                    "message": f"TP1 Target reached at {current_price:.5f}"
                }
        elif direction in ["DOWN", "SHORT", "SELL"]:
            if sl and current_price >= sl:
                return "COMPLETED", True, {
                    "outcome": "LOSS",
                    "exit_price": current_price,
                    "exit_time": now,
                    "reason": f"Stop Loss hit at {current_price:.5f}"
                }
            if tp3 and current_price <= tp3:
                return "COMPLETED", True, {
                    "outcome": "WIN",
                    "exit_price": current_price,
                    "exit_time": now,
                    "reason": f"TP3 Target reached at {current_price:.5f}"
                }
            if tp1 and current_price <= tp1 and current_status == "ACTIVE":
                return "UPDATE", False, {
                    "event": "TP1_REACHED",
                    "price": current_price,
                    "message": f"TP1 Target reached at {current_price:.5f}"
                }

        return "ACTIVE", False, {"price": current_price, "message": "Signal actively tracking"}
