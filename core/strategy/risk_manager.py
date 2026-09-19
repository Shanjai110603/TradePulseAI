"""
Advanced Risk Management, Position Sizing & Circuit Breaker Engine
===================================================================
Manages daily Take Profit / Stop Loss circuit breakers, Martingale recovery
step calculations, and compounding turnover position sizing.
"""
import logging
import threading
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("TradePulse.RiskManager")


class RiskManager:
    """Manages session goals, loss mitigation, and position sizing recommendations."""

    def __init__(self):
        self.enabled: bool = True

        # Position Sizing
        self.base_stake: float = 10.0
        self.stake_mode: str = "fixed"  # 'fixed' or 'percent'
        self.stake_percent: float = 2.0

        # Martingale Recovery
        self.martingale_enabled: bool = False
        self.martingale_mode: str = "signal"  # 'signal' (Next Signal) or 'expiry' (Next Expiry)
        self.martingale_multiplier: float = 2.0
        self.martingale_max_steps: int = 3

        # Compounding
        self.compounding_enabled: bool = False
        self.compounding_turnover_pct: float = 20.0
        self.compounding_max_steps: int = 3

        # Session Goals & Circuit Breakers
        self.daily_tp_enabled: bool = False
        self.daily_tp_amount: float = 100.0
        self.daily_sl_enabled: bool = False
        self.daily_sl_amount: float = 50.0

        # Session Telemetry State
        self._lock = threading.RLock()
        self.session_trades: int = 0
        self.session_wins: int = 0
        self.session_losses: int = 0
        self.session_draws: int = 0
        self.session_net_pnl: float = 0.0
        self.current_loss_streak: int = 0
        self.current_win_streak: int = 0
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_reason: Optional[str] = None

    def configure(
        self,
        enabled: Optional[bool] = None,
        base_stake: Optional[float] = None,
        stake_mode: Optional[str] = None,
        stake_percent: Optional[float] = None,
        martingale_enabled: Optional[bool] = None,
        martingale_mode: Optional[str] = None,
        martingale_multiplier: Optional[float] = None,
        martingale_max_steps: Optional[int] = None,
        compounding_enabled: Optional[bool] = None,
        compounding_turnover_pct: Optional[float] = None,
        daily_tp_enabled: Optional[bool] = None,
        daily_tp_amount: Optional[float] = None,
        daily_sl_enabled: Optional[bool] = None,
        daily_sl_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Dynamically updates risk management preferences."""
        with self._lock:
            if enabled is not None:
                self.enabled = bool(enabled)
            if base_stake is not None:
                self.base_stake = max(1.0, float(base_stake))
            if stake_mode is not None and stake_mode.lower() in ("fixed", "percent"):
                self.stake_mode = stake_mode.lower()
            if stake_percent is not None:
                self.stake_percent = max(0.5, min(20.0, float(stake_percent)))
            if martingale_enabled is not None:
                self.martingale_enabled = bool(martingale_enabled)
            if martingale_mode is not None and martingale_mode.lower() in ("signal", "expiry"):
                self.martingale_mode = martingale_mode.lower()
            if martingale_multiplier is not None:
                self.martingale_multiplier = max(1.1, min(5.0, float(martingale_multiplier)))
            if martingale_max_steps is not None:
                self.martingale_max_steps = max(1, min(10, int(martingale_max_steps)))
            if compounding_enabled is not None:
                self.compounding_enabled = bool(compounding_enabled)
            if compounding_turnover_pct is not None:
                self.compounding_turnover_pct = max(5.0, min(100.0, float(compounding_turnover_pct)))
            if daily_tp_enabled is not None:
                self.daily_tp_enabled = bool(daily_tp_enabled)
            if daily_tp_amount is not None:
                self.daily_tp_amount = max(1.0, float(daily_tp_amount))
            if daily_sl_enabled is not None:
                self.daily_sl_enabled = bool(daily_sl_enabled)
            if daily_sl_amount is not None:
                self.daily_sl_amount = max(1.0, float(daily_sl_amount))

        logger.info(
            f"[RISK MANAGER] Config updated: enabled={self.enabled}, base_stake=${self.base_stake}, "
            f"martingale=(on={self.martingale_enabled}, mult={self.martingale_multiplier}x, max={self.martingale_max_steps}), "
            f"daily_tp=(on={self.daily_tp_enabled}, ${self.daily_tp_amount}), "
            f"daily_sl=(on={self.daily_sl_enabled}, ${self.daily_sl_amount})"
        )
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Returns current configuration dictionary."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "base_stake": self.base_stake,
                "stake_mode": self.stake_mode,
                "stake_percent": self.stake_percent,
                "martingale_enabled": self.martingale_enabled,
                "martingale_mode": self.martingale_mode,
                "martingale_multiplier": self.martingale_multiplier,
                "martingale_max_steps": self.martingale_max_steps,
                "compounding_enabled": self.compounding_enabled,
                "compounding_turnover_pct": self.compounding_turnover_pct,
                "daily_tp_enabled": self.daily_tp_enabled,
                "daily_tp_amount": self.daily_tp_amount,
                "daily_sl_enabled": self.daily_sl_enabled,
                "daily_sl_amount": self.daily_sl_amount
            }

    def get_recommended_stake(self) -> Dict[str, Any]:
        """Calculates recommended trade stake and Martingale step for upcoming signal."""
        with self._lock:
            if not self.enabled:
                return {
                    "stake": self.base_stake,
                    "step": 1,
                    "is_martingale": False,
                    "is_compound": False,
                    "note": "Standard base stake"
                }

            # Martingale sizing after consecutive losses
            if self.martingale_enabled and self.current_loss_streak > 0:
                step = min(self.current_loss_streak + 1, self.martingale_max_steps)
                step_idx = step - 1
                rec_stake = round(self.base_stake * (self.martingale_multiplier ** step_idx), 2)
                return {
                    "stake": rec_stake,
                    "step": step,
                    "is_martingale": True,
                    "is_compound": False,
                    "note": f"Martingale Step {step}/{self.martingale_max_steps} ({self.martingale_multiplier}x)"
                }

            # Compounding sizing after win
            if self.compounding_enabled and self.current_win_streak > 0:
                comp_step = min(self.current_win_streak, self.compounding_max_steps)
                extra = self.base_stake * (self.compounding_turnover_pct / 100.0) * comp_step
                rec_stake = round(self.base_stake + extra, 2)
                return {
                    "stake": rec_stake,
                    "step": comp_step,
                    "is_martingale": False,
                    "is_compound": True,
                    "note": f"Compounding Step {comp_step} (+{self.compounding_turnover_pct:.0f}% turnover)"
                }

            return {
                "stake": self.base_stake,
                "step": 1,
                "is_martingale": False,
                "is_compound": False,
                "note": "Standard base stake"
            }

    def record_trade_outcome(self, outcome: str, payout_pct: float = 85.0, stake: Optional[float] = None):
        """Records result of a completed trade to update streaks, PnL, and circuit breakers."""
        with self._lock:
            act_stake = float(stake or self.base_stake)
            self.session_trades += 1
            out_upper = str(outcome or "").upper()

            if "WIN" in out_upper:
                self.session_wins += 1
                self.current_win_streak += 1
                self.current_loss_streak = 0
                profit = round(act_stake * (float(payout_pct) / 100.0), 2)
                self.session_net_pnl = round(self.session_net_pnl + profit, 2)
                logger.info(f"[RISK MANAGER] WIN recorded (+${profit}). Session PnL: ${self.session_net_pnl:+.2f}")
            elif "LOSS" in out_upper:
                self.session_losses += 1
                self.current_loss_streak += 1
                self.current_win_streak = 0
                loss = round(act_stake, 2)
                self.session_net_pnl = round(self.session_net_pnl - loss, 2)
                logger.info(f"[RISK MANAGER] LOSS recorded (-${loss}). Session PnL: ${self.session_net_pnl:+.2f}")
            else:
                self.session_draws += 1

            # Check Circuit Breakers
            self._evaluate_circuit_breakers()

    def _evaluate_circuit_breakers(self):
        """Evaluates whether session PnL has reached Take Profit or Stop Loss limits."""
        if not self.enabled:
            return

        if self.daily_tp_enabled and self.session_net_pnl >= self.daily_tp_amount:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = f"Daily Take Profit target of +${self.daily_tp_amount:.2f} reached (+${self.session_net_pnl:.2f})"
            logger.warning(f"🎯 [CIRCUIT BREAKER] {self.circuit_breaker_reason}")

        elif self.daily_sl_enabled and self.session_net_pnl <= -abs(self.daily_sl_amount):
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = f"Daily Stop Loss limit of -${self.daily_sl_amount:.2f} hit (${self.session_net_pnl:.2f})"
            logger.warning(f"🛑 [CIRCUIT BREAKER] {self.circuit_breaker_reason}")

    def check_circuit_breaker(self) -> Tuple[bool, Optional[str]]:
        """Returns (is_active, reason_message) indicating whether scanner should pause."""
        with self._lock:
            if not self.enabled:
                return False, None
            return self.circuit_breaker_active, self.circuit_breaker_reason

    def reset_session(self):
        """Resets session telemetry and clears active circuit breakers."""
        with self._lock:
            self.session_trades = 0
            self.session_wins = 0
            self.session_losses = 0
            self.session_draws = 0
            self.session_net_pnl = 0.0
            self.current_loss_streak = 0
            self.current_win_streak = 0
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = None
        logger.info("[RISK MANAGER] Daily session metrics reset.")

    def get_session_metrics(self) -> Dict[str, Any]:
        """Returns current session telemetry for frontend display and Telegram alerts."""
        with self._lock:
            wr = round((self.session_wins / self.session_trades * 100.0), 1) if self.session_trades > 0 else 0.0
            rec = self.get_recommended_stake()
            return {
                "trades": self.session_trades,
                "trades_count": self.session_trades,
                "wins": self.session_wins,
                "losses": self.session_losses,
                "draws": self.session_draws,
                "win_rate": wr,
                "net_pnl": self.session_net_pnl,
                "daily_pnl": self.session_net_pnl,
                "next_recommended_stake": rec.get("stake", self.base_stake),
                "current_martingale_step": rec.get("step", 1),
                "loss_streak": self.current_loss_streak,
                "win_streak": self.current_win_streak,
                "circuit_breaker_active": self.circuit_breaker_active,
                "circuit_breaker_reason": self.circuit_breaker_reason
            }
