# Backtesting Engine & Simulation

## Methodology

The TradePulse AI backtesting engine operates using a strict **event-driven, chronological replay model**:
- **Look-Ahead Bias Prevention**: At candle step $i$, the engine is given only historical candles up to index $i$ ($[0 \dots i]$). Future candles are strictly obscured.
- **Warmup Period**: 25 candles are used for indicator initialization (e.g. 20-period moving averages and 14-period RSI).
- **Execution & Outcome Tracking**:
  - **Fixed-Time / Digital Options**: Follows price to $i + \text{expiry\_candles}$ and computes win/loss/tie based on direction.
  - **Standard Markets**: Traverses candle by candle to evaluate Take Profit 1-3 vs. Stop Loss triggers.
- **Metrics Computed**: Total signals, Win rate %, Profit factor, Max drawdown %, Equity curve data points, and trade logs.
