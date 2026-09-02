# TradePulse Quotex Assistant (Local AI Browser + Telegram Remote)

A dedicated Windows Desktop Application inspired by the **Local AI Browser + Telegram Assistant** architecture.

It combines an undetectable Chromium controller (CDP), deterministic Multi-Timeframe Strategy Engine (`MTF_ENGULFING_1M`), real-time chart screenshot capture, and a **Two-Way Interactive Telegram Remote**.

---

## 🔒 Architectural Safe Mode

**Zero Trade Execution**: The application has no trading or transaction tools. It solely observes the Quotex chart, extracts live prices, evaluates strategy confluence, and sends research alerts to Telegram.

---

## ⚡ Core Features

1. **Undetectable Chromium Control (CDP)**:
   - Controls Chrome or Edge on port `9222` with persistent user profile.
   - Cloudflare-friendly: uses genuine browser cookies and sessions.

2. **Multi-Tier Self-Healing Asset Switcher**:
   - 4-tier selector fallback: Class/ID tabs ➔ text-matching ➔ '+' asset modal search ➔ direct navigation.
   - Cycles through all 20+ high-payout OTC pairs automatically.

3. **Deterministic Strategy 1 (`MTF_ENGULFING_1M`) Engine**:
   - 1M chart execution with 5M trend alignment via Exponential Moving Average (EMA 20).
   - Solid body ratio $> 65\%$, opposing wick filter $\le 30\%$, Doji rejection, and anomaly spike protection.
   - 2-Minute expiry time synchronization.

4. **Real-Time Live Chart Screenshots**:
   - On confirmed confluence, commands CDP to snap a high-resolution screenshot of the actual Quotex chart.
   - Uploads the chart photo directly to Telegram attached to the VIP Signal Card.

5. **Two-Way Interactive Telegram Remote Control**:
   - Control the desktop browser directly from your phone in `@TradePulse_QuotexBot`!

| Telegram Command | Action Performed |
|---|---|
| **`/screenshot`** | Takes an instant live screenshot of the active chart and replies with the photo |
| **`/status`** | Returns active pair, scanning telemetry, ticks, candle counts, and uptime |
| **`/markets`** | Lists live prices and payouts of all 20 monitored OTC pairs |
| **`/switch <pair>`** | Commands browser to navigate to that pair (e.g. `/switch EUR/USD`) |
| **`/pause` & `/resume`** | Remotely pauses or resumes the automated scanner |
| **`/analyze`** | Runs on-demand confluence evaluation on the active chart with explainability breakdown |

---

## 🚀 How to Run (AWS Windows Server or Local)

1. Make sure Python 3.10+ and Google Chrome are installed.
2. In PowerShell:
   ```powershell
   cd C:\TradePulse
   git pull origin main
   cd C:\TradePulse\scanner
   pip install httpx websockets
   python quotex_scanner.py
   ```
*(Or simply double-click `START_SCANNER.bat` in File Explorer)*

3. Click **▶ START SCANNER** in the app.
4. Log into Quotex once in Chrome (if needed).
5. The assistant handles the rest automatically!
