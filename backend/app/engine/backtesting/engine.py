import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine
from app.engine.ai.mock_ai import MockAIProvider
from app.engine.filters.engine import UserFilterEngine


class BacktestingEngine:
    """
    Event-driven chronological backtester.
    Replays historical candles sequentially to prevent look-ahead bias.
    """

    @classmethod
    async def run_backtest(
        cls,
        pattern_dict: Dict[str, Any],
        candles: List[Candle],
        initial_capital: float = 1000.0,
        fixed_risk_per_trade: float = 20.0
    ) -> Dict[str, Any]:
        """
        Executes backtest over historical candles.
        Returns full performance metrics, win rate, equity curve, and individual trade logs.
        """
        if len(candles) < 30:
            return {
                "status": "FAILED",
                "reason": "Insufficient candles for meaningful backtesting (minimum 30 required)",
                "total_signals": 0,
                "win_rate_percentage": 0.0,
                "signals_log": [],
                "equity_curve": []
            }

        market_id = pattern_dict.get("market_id", "digital_options")
        direction = pattern_dict.get("direction", "DOWN").upper()
        target_cfg = pattern_dict.get("target_config", {})
        expiry_candles = target_cfg.get("duration_candles", 5)

        trades: List[Dict[str, Any]] = []
        equity = initial_capital
        equity_curve: List[Dict[str, Any]] = [
            {"timestamp": datetime.fromtimestamp(candles[0].timestamp, tz=timezone.utc).isoformat(), "equity": equity, "trade_number": 0}
        ]

        wins = 0
        losses = 0
        ties = 0
        peak_equity = initial_capital
        max_drawdown = 0.0

        ai_mock = MockAIProvider()

        # Step through candles chronologically
        # Warmup period of 25 candles for indicator stabilization
        i = 25
        while i < len(candles) - expiry_candles:
            candle_window = candles[: i + 1]
            
            # 1. Deterministic Rule Engine
            rule_res = PatternRuleEngine.evaluate_pattern(pattern_dict, candle_window)
            if rule_res.get("matched", False):
                entry_candle = candles[i]
                entry_price = entry_candle.close
                entry_time = datetime.fromtimestamp(entry_candle.timestamp, tz=timezone.utc)

                # Optional AI evaluation
                ai_res = await ai_mock.analyze_signal(
                    candidate_data={
                        "direction": direction,
                        "asset_symbol": pattern_dict.get("asset_symbol", "EUR/USD"),
                        "reference_price": entry_price,
                        "timeframe": pattern_dict.get("timeframe", "1M"),
                        "pattern_name": pattern_dict.get("name", "Pattern")
                    },
                    technical_snapshot=rule_res.get("technical_snapshot", {})
                )

                # Filter evaluation
                passed, _, _ = UserFilterEngine.evaluate_filters(
                    candidate_data={"direction": direction},
                    ai_analysis=ai_res,
                    pattern_config=pattern_dict
                )

                if passed:
                    # Execute simulated trade to expiry
                    exit_index = i + expiry_candles
                    exit_candle = candles[exit_index]
                    exit_price = exit_candle.close
                    exit_time = datetime.fromtimestamp(exit_candle.timestamp, tz=timezone.utc)

                    if direction in ["DOWN", "SHORT", "SELL"]:
                        if exit_price < entry_price:
                            outcome = "WIN"
                            pnl_amount = fixed_risk_per_trade * 0.85  # Standard payout ratio
                            wins += 1
                        elif exit_price > entry_price:
                            outcome = "LOSS"
                            pnl_amount = -fixed_risk_per_trade
                            losses += 1
                        else:
                            outcome = "TIE"
                            pnl_amount = 0.0
                            ties += 1
                    else:  # UP / LONG / BUY
                        if exit_price > entry_price:
                            outcome = "WIN"
                            pnl_amount = fixed_risk_per_trade * 0.85
                            wins += 1
                        elif exit_price < entry_price:
                            outcome = "LOSS"
                            pnl_amount = -fixed_risk_per_trade
                            losses += 1
                        else:
                            outcome = "TIE"
                            pnl_amount = 0.0
                            ties += 1

                    equity += pnl_amount
                    peak_equity = max(peak_equity, equity)
                    drawdown = (peak_equity - equity) / peak_equity * 100.0 if peak_equity > 0 else 0.0
                    max_drawdown = max(max_drawdown, drawdown)

                    trade_record = {
                        "trade_number": len(trades) + 1,
                        "candle_index": i,
                        "entry_time": entry_time.isoformat(),
                        "entry_price": entry_price,
                        "exit_time": exit_time.isoformat(),
                        "exit_price": exit_price,
                        "direction": direction,
                        "outcome": outcome,
                        "pnl_amount": round(pnl_amount, 2),
                        "pnl_percentage": round(((exit_price - entry_price) / entry_price) * 100 if direction == "UP" else ((entry_price - exit_price) / entry_price) * 100, 4),
                        "ai_score": ai_res.score,
                        "equity_after": round(equity, 2)
                    }
                    trades.append(trade_record)

                    equity_curve.append({
                        "timestamp": exit_time.isoformat(),
                        "equity": round(equity, 2),
                        "trade_number": len(trades)
                    })

                    # Advance past the trade duration to avoid overlapping signals
                    i += expiry_candles
                    continue

            i += 1

        total_trades = len(trades)
        decided_trades = wins + losses
        win_rate = (wins / decided_trades * 100.0) if decided_trades > 0 else 0.0

        total_gain = sum(t["pnl_amount"] for t in trades if t["pnl_amount"] > 0)
        total_loss = abs(sum(t["pnl_amount"] for t in trades if t["pnl_amount"] < 0))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.9 if total_gain > 0 else 0.0)

        return {
            "status": "COMPLETED",
            "total_signals": total_trades,
            "winning_signals": wins,
            "losing_signals": losses,
            "tie_signals": ties,
            "win_rate_percentage": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_percentage": round(max_drawdown, 2),
            "ending_equity": round(equity, 2),
            "return_percentage": round(((equity - initial_capital) / initial_capital) * 100.0, 2),
            "average_duration_seconds": expiry_candles * 60,
            "signals_log": trades,
            "equity_curve": equity_curve,
            "metrics": {
                "total_trades": total_trades,
                "win_count": wins,
                "loss_count": losses,
                "tie_count": ties,
                "profit_factor": round(profit_factor, 2),
                "max_drawdown": round(max_drawdown, 2),
                "net_profit": round(equity - initial_capital, 2)
            }
        }
