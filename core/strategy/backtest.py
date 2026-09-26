"""
TradePulse Historical Quick-Tester & Backtest Engine
Evaluates user-defined custom strategies across authentic historical candles
in memory and computes expected win rate %, signal count, and profit factor.
"""
import bisect
from typing import Any, Dict, List, Optional
from core.indicators.engine import TechnicalIndicatorEngine
from core.models.candle import Candle, CandleStore
from core.strategy.compiler import StrategyCompiler
from core.strategy.rules_ast import PatternRuleEngine
from core.strategy.schema import UserStrategy


class HistoricalBacktestEngine:
    """
    Simulates visual/AST strategies against authentic historical candlestick buffers.
    Calculates empirical win rates, profit factors, and trade outcome distributions.
    """

    @staticmethod
    def test_strategy_on_asset(
        strategy: UserStrategy,
        candles_1m: List[Candle],
        candles_5m: Optional[List[Candle]] = None,
        payout_pct: float = 85.0
    ) -> Dict[str, Any]:
        """
        Backtests strategy on a chronological sequence of candles.
        Simulates forward trade execution for the configured expiry duration.
        """
        if len(candles_1m) < 25:
            return {"error": "Insufficient candle depth (need at least 25 bars)"}

        compiled_ast = StrategyCompiler.compile_strategy_ast(strategy)
        expiry_bars = max(1, strategy.expiry_minutes)

        total_signals = 0
        wins = 0
        losses = 0
        draws = 0
        results_log = []
        is_strat_5m = (strategy.timeframe or "1M").upper() == "5M"

        # Step through history (leaving room for trade expiry resolution)
        for i in range(20, len(candles_1m) - expiry_bars):
            history_slice = candles_1m[:i + 1]
            trigger_candle = history_slice[-1]
            entry_price = trigger_candle.close

            is_5m_close = ((trigger_candle.timestamp + 60) % 300 == 0)
            if is_strat_5m and not is_5m_close:
                continue

            # Synthesize higher timeframes strictly from history_slice (zero lookahead bias)
            c_3m_slice = CandleStore._synthesize_timeframe(history_slice, 180)
            c_5m_slice = CandleStore._synthesize_timeframe(history_slice, 300)
            c_15m_slice = CandleStore._synthesize_timeframe(history_slice, 900)

            mtf_dict = {
                "1M": history_slice,
                "3M": c_3m_slice,
                "5M": c_5m_slice,
                "15M": c_15m_slice
            }

            if is_strat_5m:
                if len(c_5m_slice) < 15:
                    continue
                eval_candles = c_5m_slice
                eval_snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(c_5m_slice)
            else:
                eval_candles = history_slice
                eval_snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(history_slice)

            directions_to_test = ["CALL", "PUT"] if strategy.direction == "BOTH" else [strategy.direction]
            for direction in directions_to_test:
                passed, reason, details = PatternRuleEngine.evaluate_node(
                    compiled_ast,
                    eval_candles,
                    multi_timeframe_candles=mtf_dict,
                    technical_snapshot=eval_snapshot,
                    direction_context=direction
                )

                if passed:
                    total_signals += 1
                    # Resolve outcome at future bar
                    exit_candle = candles_1m[i + expiry_bars]
                    exit_price = exit_candle.close

                    is_call = direction.upper() in ["CALL", "UP", "BUY"]
                    outcome = "DRAW"
                    if is_call:
                        if exit_price > entry_price:
                            outcome = "WIN"
                            wins += 1
                        elif exit_price < entry_price:
                            outcome = "LOSS"
                            losses += 1
                        else:
                            draws += 1
                    else:  # PUT
                        if exit_price < entry_price:
                            outcome = "WIN"
                            wins += 1
                        elif exit_price > entry_price:
                            outcome = "LOSS"
                            losses += 1
                        else:
                            draws += 1

                    # Calculate MFE (Max Favorable Excursion) & MAE (Max Adverse Excursion)
                    window_candles = candles_1m[i + 1:i + 1 + expiry_bars]
                    if window_candles:
                        highs = [c.high for c in window_candles]
                        lows = [c.low for c in window_candles]
                        max_window_price = max(highs)
                        min_window_price = min(lows)
                    else:
                        max_window_price = exit_price
                        min_window_price = exit_price

                    if is_call:
                        mfe = round(max(0.0, max_window_price - entry_price), 5)
                        mae = round(max(0.0, entry_price - min_window_price), 5)
                    else:
                        mfe = round(max(0.0, entry_price - min_window_price), 5)
                        mae = round(max(0.0, max_window_price - entry_price), 5)

                    results_log.append({
                        "bar_index": i,
                        "timestamp": trigger_candle.timestamp,
                        "direction": direction,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "outcome": outcome,
                        "mfe": mfe,
                        "mae": mae,
                    })
                    break  # One signal per candle max

        win_rate = (wins / total_signals * 100.0) if total_signals > 0 else 0.0
        warning = None
        if total_signals < 20:
            warning = f"Sample size ({total_signals} signals). Live forward testing advised."

        # Quantitative Equity Simulation & Profit Factor
        base_stake = 10.0
        b_payout = payout_pct / 100.0
        gross_profit = wins * (base_stake * b_payout)
        gross_loss = losses * base_stake
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        net_profit = round(gross_profit - gross_loss, 2)

        # Drawdown calculation
        peak = 0.0
        current_eq = 0.0
        max_dd = 0.0
        equity_curve = [0.0]

        for trade in results_log:
            if trade["outcome"] == "WIN":
                current_eq += base_stake * b_payout
            elif trade["outcome"] == "LOSS":
                current_eq -= base_stake
            equity_curve.append(round(current_eq, 2))
            if current_eq > peak:
                peak = current_eq
            dd = peak - current_eq
            if dd > max_dd:
                max_dd = dd

        # Avg MFE / MAE
        avg_mfe = round(sum(t.get("mfe", 0) for t in results_log) / total_signals, 5) if total_signals > 0 else 0.0
        avg_mae = round(sum(t.get("mae", 0) for t in results_log) / total_signals, 5) if total_signals > 0 else 0.0

        # Mathematical EV per $10 stake
        p = win_rate / 100.0
        q = 1.0 - p
        ev_per_trade = round((p * b_payout * base_stake) - (q * base_stake), 2)

        return {
            "strategy_name": strategy.name,
            "candles_analyzed": len(candles_1m),
            "total_signals": total_signals,
            "sample_size_warning": warning,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round(win_rate, 1),
            "profit_factor": profit_factor,
            "net_profit": net_profit,
            "max_drawdown": round(max_dd, 2),
            "ev_per_trade": ev_per_trade,
            "avg_mfe": avg_mfe,
            "avg_mae": avg_mae,
            "payout_pct": payout_pct,
            "equity_curve": equity_curve[-30:],
            "signals": results_log[-30:]  # Last 30 triggers
        }

