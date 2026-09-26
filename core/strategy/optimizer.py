"""
TradePulse Quantitative Parameter Optimizer & Strategy Tournament Engine
=======================================================================
Inspired by VectorBT, StrategyQuant, and Trading Strategy Optimizer.
Provides high-speed pure-Python grid search parameter optimization,
robustness verification, and Monte Carlo shuffle validation without external C/C++ dependencies.
"""
import itertools
import random
from typing import Any, Dict, List, Optional
from core.models.candle import Candle
from core.indicators.engine import TechnicalIndicatorEngine
from core.strategy.quant_ev import QuantEVFilter


class StrategyOptimizer:
    """
    Evaluates multi-parameter combination spaces against historical candle sets
    to discover optimal, mathematically positive-EV indicator parameters.
    """

    @staticmethod
    def run_rsi_bollinger_grid_search(
        candles: List[Candle],
        rsi_periods: List[int] = [7, 10, 14, 21],
        rsi_ob_levels: List[float] = [70.0, 75.0, 80.0],
        rsi_os_levels: List[float] = [30.0, 25.0, 20.0],
        bb_deviations: List[float] = [1.8, 2.0, 2.2, 2.5],
        payout_pct: float = 85.0
    ) -> List[Dict[str, Any]]:
        """
        High-speed parameter sweep across RSI & Bollinger Band combinations.
        Returns ranked parameter configurations sorted by Expected Value and Win Rate.
        """
        if len(candles) < 50:
            return []

        results: List[Dict[str, Any]] = []
        payout_mult = payout_pct / 100.0

        for rsi_p, ob, os_lvl, bb_dev in itertools.product(rsi_periods, rsi_ob_levels, rsi_os_levels, bb_deviations):
            wins = 0
            losses = 0
            ties = 0

            # Step through candles (walk forward evaluation)
            min_warmup = max(rsi_p + 1, 20) + 1
            for i in range(min_warmup, len(candles) - 1):
                sub_candles = candles[:i]
                target_candle = candles[i]

                rsi = TechnicalIndicatorEngine.calculate_rsi(sub_candles, period=rsi_p)
                bb = TechnicalIndicatorEngine.calculate_bollinger_bands(sub_candles, period=20, std_dev_multiplier=bb_dev)

                if rsi is None or bb is None:
                    continue

                curr_close = sub_candles[-1].close
                signal = None

                # Oversold bounce condition
                if curr_close <= bb["lower"] and rsi <= os_lvl:
                    signal = "CALL"
                # Overbought rejection condition
                elif curr_close >= bb["upper"] and rsi >= ob:
                    signal = "PUT"

                if not signal:
                    continue

                # Evaluate next bar outcome
                if signal == "CALL":
                    if target_candle.close > sub_candles[-1].close:
                        wins += 1
                    elif target_candle.close < sub_candles[-1].close:
                        losses += 1
                    else:
                        ties += 1
                elif signal == "PUT":
                    if target_candle.close < sub_candles[-1].close:
                        wins += 1
                    elif target_candle.close > sub_candles[-1].close:
                        losses += 1
                    else:
                        ties += 1

            total_trades = wins + losses + ties
            if total_trades < 3:
                continue

            decisive_trades = wins + losses
            win_rate = (wins / decisive_trades * 100.0) if decisive_trades > 0 else 0.0
            profit = (wins * payout_mult) - (losses * 1.0)
            gross_loss = float(losses * 1.0)
            profit_factor = round((wins * payout_mult) / gross_loss, 2) if gross_loss > 0 else (99.0 if wins > 0 else 0.0)

            p_win = win_rate / 100.0
            p_loss = 1.0 - p_win
            ev_per_trade = round((p_win * payout_mult) - (p_loss * 1.0), 4)

            # Half-Kelly stake advice
            be_rate = QuantEVFilter.calculate_breakeven_rate(payout_pct)
            b = payout_mult
            full_kelly = max(0.0, (p_win * b - p_loss) / b) if b > 0 else 0.0
            half_kelly_pct = round((full_kelly / 2.0) * 100.0, 2)

            results.append({
                "rsi_period": rsi_p,
                "rsi_overbought": ob,
                "rsi_oversold": os_lvl,
                "bb_deviation": bb_dev,
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_rate": round(win_rate, 2),
                "profit_factor": profit_factor,
                "net_profit_units": round(profit, 2),
                "expected_value_per_trade": ev_per_trade,
                "breakeven_win_rate": be_rate,
                "has_positive_edge": win_rate > be_rate,
                "half_kelly_pct": half_kelly_pct
            })

        # Sort by mathematical Expected Value descending, then Win Rate
        results.sort(key=lambda x: (x["expected_value_per_trade"], x["win_rate"]), reverse=True)
        return results

    @staticmethod
    def run_monte_carlo_permutation_test(
        wins: int,
        losses: int,
        payout_pct: float = 85.0,
        simulations: int = 500,
        stake: float = 10.0
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo trade order reshuffling to test strategy drawdown resilience
        and simulate worst-case consecutive loss streaks.
        """
        total = wins + losses
        if total < 5:
            return {
                "simulations": 0,
                "max_consecutive_losses_p95": 0,
                "max_drawdown_p95": 0.0,
                "median_profit": 0.0,
                "ruin_probability_pct": 0.0
            }

        payout_mult = payout_pct / 100.0
        profit_per_win = stake * payout_mult
        loss_per_loss = -stake

        trade_outcomes = [profit_per_win] * wins + [loss_per_loss] * losses
        max_drawdowns: List[float] = []
        consecutive_losses_list: List[int] = []
        final_profits: List[float] = []

        for _ in range(simulations):
            shuffled = list(trade_outcomes)
            random.shuffle(shuffled)

            equity = 0.0
            peak = 0.0
            max_dd = 0.0
            current_loss_streak = 0
            max_loss_streak = 0

            for pnl in shuffled:
                equity += pnl
                if equity > peak:
                    peak = equity
                dd = peak - equity
                if dd > max_dd:
                    max_dd = dd

                if pnl < 0:
                    current_loss_streak += 1
                    if current_loss_streak > max_loss_streak:
                        max_loss_streak = current_loss_streak
                else:
                    current_loss_streak = 0

            max_drawdowns.append(max_dd)
            consecutive_losses_list.append(max_loss_streak)
            final_profits.append(equity)

        max_drawdowns.sort()
        consecutive_losses_list.sort()
        final_profits.sort()

        p95_idx = int(simulations * 0.95)
        median_idx = int(simulations * 0.50)

        return {
            "simulations": simulations,
            "max_consecutive_losses_p95": consecutive_losses_list[p95_idx],
            "max_drawdown_p95": round(max_drawdowns[p95_idx], 2),
            "median_profit": round(final_profits[median_idx], 2),
            "ruin_probability_pct": round(sum(1 for p in final_profits if p < 0) / simulations * 100.0, 2)
        }
