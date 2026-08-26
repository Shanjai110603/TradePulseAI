# 18-Step Pattern Strategy Builder Wizard

## Overview

The Pattern Strategy Builder allows users to configure complete trading strategies combining visual reference images, deterministic rule parameters, technical indicator criteria, multi-timeframe trend requirements, and AI quantitative filters.

## Strategy Configuration Breakdown

1. **Pattern Identification**: Name, description, and setup mechanics.
2. **Visual Reference Upload**: Upload chart image (PNG/JPG/WebP up to 5MB).
3. **Market Category**: Digital Options Style, Crypto, Forex, Stocks.
4. **Asset Selection**: Multi-asset asset assignment (e.g. `EUR/USD`, `BTC/USDT`).
5. **Direction**: `UP` (LONG / CALL) or `DOWN` (SHORT / PUT).
6. **Primary Timeframe**: `1M`, `5M`, `15M`, `1H`.
7. **Multi-Timeframe Trend Requirements**: Base timeframe trend + 5M/15M alignment.
8. **Momentum & Oscillators**: RSI min/max bands, ADX strength, MACD bias.
9. **Volume Rules**: 20-period moving average ratio confirmation.
10. **Candlestick & Breakout Logic**: Number of base candles, S/R swing detection source, close vs wick confirmation.
11. **Expiry & Targets**: Fixed time duration or Risk-Reward TP1-TP3 / Stop Loss.
12. **AI Analysis Requirements**: Minimum AI score (0-100), required confidence level (`LOW`, `MODERATE`, `HIGH`), and bias matching.
13. **Notification Configuration**: Instant Telegram alert dispatch.
14. **Review & Audit**: Visual confirmation of all AST rules.
15. **Save & Versioning**: Automatic immutable version snapshot created in database.
16. **Instant Backtesting Replay**: One-click transition to the backtesting terminal.
