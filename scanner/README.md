# TradePulse Quotex Multi-Currency Scanner

A standalone Windows application that automatically scans **20+ Quotex OTC currencies** 
and streams live OHLC candles to the TradePulse Telegram Bot.

## How It Works

1. **Launches Chrome** with remote debugging (CDP protocol)
2. **Opens Quotex** trading page in a real Chrome browser (undetectable)
3. **Automatically rotates** through all 20+ OTC currency pairs
4. **Reads live prices** from the Quotex DOM every 2-3 seconds
5. **Accumulates ticks** into proper 1-minute OHLCV candles
6. **Streams candles** to the TradePulse bot at `http://127.0.0.1:8000`
7. **Bot evaluates** MTF_ENGULFING_1M strategy and fires Telegram alerts

## Quick Start

### On Your AWS Windows Server:

1. Make sure the TradePulse bot backend is running:
   ```powershell
   cd C:\TradePulse\backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. Double-click `START_SCANNER.bat` or run:
   ```powershell
   cd C:\TradePulse\scanner
   python quotex_scanner.py
   ```

3. Chrome will open automatically — **log into Quotex** if not already logged in.

4. The scanner will begin cycling through currencies and streaming to the bot!

## Currencies Scanned

| # | Currency | Pair Code |
|---|----------|-----------|
| 1 | EUR/USD (OTC) | EURUSD_otc |
| 2 | GBP/USD (OTC) | GBPUSD_otc |
| 3 | USD/JPY (OTC) | USDJPY_otc |
| 4 | AUD/USD (OTC) | AUDUSD_otc |
| 5 | USD/CHF (OTC) | USDCHF_otc |
| 6 | USD/CAD (OTC) | USDCAD_otc |
| 7 | NZD/USD (OTC) | NZDUSD_otc |
| 8 | EUR/GBP (OTC) | EURGBP_otc |
| 9 | EUR/JPY (OTC) | EURJPY_otc |
| 10 | GBP/JPY (OTC) | GBPJPY_otc |
| 11 | AUD/CAD (OTC) | AUDCAD_otc |
| 12 | AUD/JPY (OTC) | AUDJPY_otc |
| 13 | USD/INR (OTC) | USDINR_otc |
| 14 | USD/BRL (OTC) | USDBRL_otc |
| 15 | USD/PKR (OTC) | USDPKR_otc |
| 16 | USD/ZAR (OTC) | USDZAR_otc |
| 17 | NZD/CAD (OTC) | NZDCAD_otc |
| 18 | USD/MXN (OTC) | USDMXN_otc |
| 19 | USD/TRY (OTC) | USDTRY_otc |
| 20 | USD/EGP (OTC) | USDEGP_otc |

## Requirements

- Python 3.10+
- Google Chrome (already installed on the server)
- `httpx` and `websockets` packages (auto-installed by the batch file)
