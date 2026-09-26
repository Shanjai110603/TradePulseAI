# TradePulse Personal Edition — Comprehensive User Manual & Setup Guide

This documentation provides a complete, step-by-step guide for configuring, running, and trading with **TradePulse Personal Edition**, the dedicated, 100% Real Forex (Zero OTC) algorithmic trading workstation.

---

## 📑 Table of Contents

1. [System Architecture & Core Philosophy](#1-system-architecture--core-philosophy)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [First-Time Installation & Launch](#3-first-time-installation--launch)
4. [Connecting Your Personal Telegram Bot](#4-connecting-your-personal-telegram-bot)
5. [Embedded Quotex Terminal Docking & Login](#5-embedded-quotex-terminal-docking--login)
6. [Message Appearance & Card Style Customizer](#6-message-appearance--card-style-customizer)
7. [In-Depth Strategy Guide: Dual Bollinger Protrusion 1M](#7-in-depth-strategy-guide-dual-bollinger-protrusion-1m)
8. [Workstation Interface Tour](#8-workstation-interface-tour)
9. [24/7 VPS Headless Deployment](#9-247-vps-headless-deployment)
10. [Troubleshooting & FAQ](#10-troubleshooting--faq)

---

## 1. System Architecture & Core Philosophy

TradePulse Personal Edition is engineered specifically for solo proprietary traders demanding extreme precision on live binary options / high-frequency Forex markets.

### Key Distinctives:
- **100% Real Interbank Forex Markets**: Only genuine interbank currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, EUR/GBP, etc.) are ingested. All broker-simulated OTC pairs are strictly disabled.
- **Zero-Latency Mathematical Engine**: Pure Python indicator calculation computing intra-candle price action, dynamic Bollinger envelope breaches, ADX market regimes, and horizontal support/resistance levels in microseconds.
- **Isolated State & Storage**: Reads and writes to `~/.tradepulse/tradepulse_personal.db`, `~/.tradepulse/strategies_personal.json`, and `~/.tradepulse/telegram_config_personal.json`.
- **Gated Safety Pipeline**: The signal broadcast scanner cannot fire unless:
  1. Quotex live account is authenticated in the embedded dock.
  2. The user explicitly toggles the scanner to `ACTIVE`.

---

## 2. Prerequisites & System Requirements

### Operating System:
- **Windows 10 / Windows 11 (64-bit)** or **Windows Server 2019/2022** (for VPS).

### Minimum Hardware:
- **CPU**: Intel Core i3 / AMD Ryzen 3 or higher.
- **RAM**: 4 GB RAM minimum (8 GB recommended for multi-tab chart rendering).
- **Disk Space**: ~200 MB free space.
- **Internet**: Stable broadband connection (<100ms latency to broker servers).

### For Source Code / Developer Execution:
- Python 3.10, 3.11, or 3.12 (64-bit).
- `pip install -r requirements.txt`

---

## 3. First-Time Installation & Launch

### Method A: Standalone Executable (Recommended for Daily Use)
1. Download or locate `TradePulsePersonal-Standalone.exe` (or the `TradePulsePersonal/` folder in `dist/`).
2. Double-click `TradePulsePersonal-Standalone.exe` to start the workstation.
3. Windows SmartScreen may show an alert on first run; click **More info** $\rightarrow$ **Run anyway**.

### Method B: Launching via Python
```powershell
# Navigate to the project root directory
cd Ai-telegrambot

# Activate virtual environment if configured
.\venv\Scripts\Activate.ps1

# Run the personal edition GUI
python main_personal.py
```

---

## 5. Connecting Your Personal Telegram Bot

Receive instant pre-alerts, execution cards with rendered candlestick charts, and trade outcome notifications in your private Telegram chat or channel.

### Step 1: Create a Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to choose a name and username (e.g., `MyForexSignalsBot`).
3. Copy the **HTTP API Token** provided by BotFather (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### Step 2: Get Your Personal Chat or Channel ID
1. For personal direct messages: Search for `@userinfobot` on Telegram, click **Start**, and copy your numerical **Id** (e.g., `987654321`).
2. For private channel / group:
   - Add your newly created bot to the channel as an **Administrator** with permission to post messages.
   - Forward a message from the channel to `@userinfobot` or use `@username_to_id_bot` to get the channel ID (usually starts with `-100...`).

### Step 3: Configure in TradePulse Personal
1. In the TradePulse Personal sidebar, click **✈️ Telegram**.
2. Paste your **Bot Token** and **Chat ID / Channel ID**.
3. Click **Save Settings** and then click **Send Test Message**.
4. Check your Telegram to verify the arrival of the test signal card.

> [!NOTE]
> **5-User Subscriber Cap**: To preserve maximum personal privacy and prevent signal reselling, Personal Edition enforces a hard cap of 5 authorized subscribers.

---

## 6. Embedded Quotex Terminal Docking & Login

TradePulse Personal embeds the native Quotex web terminal directly inside the workstation window.

```
┌────────────────────────────────────────────────────────┐
│ 🏛️ EMBEDDED QUOTEX TERMINAL                            │
│ ┌────────────────────────────────────────────────────┐ │
│ │  Quotex Web Platform                               │ │
│ │  [Email: _________________]                        │ │
│ │  [Password: ______________]                        │ │
│ │  [   LOG IN   ]                                    │ │
│ └────────────────────────────────────────────────────┘ │
│ ⚡ Status: Logged in as User | Account Balance: $2,450.00│
└────────────────────────────────────────────────────────┘
```

1. In the sidebar, navigate to **🏛️ Quotex Broker**.
2. Enter your Quotex login credentials and complete 2FA / CAPTCHA if required.
3. Once logged in, the top status bar in TradePulse will display `🏛️ Quotex: Live`.
4. The signal scanner is now unlocked and ready for activation.

---

## 7. In-Depth Strategy Guide: Dual Bollinger Protrusion 1M

The pre-loaded strategy in TradePulse Personal is the **Dual Bollinger Band Protrusion Reversal** (`DUAL_BOLLINGER_PROTRUSION_1M`).

### Indicator Settings:
- **Candle Interval**: 1-Minute (`M1`)
- **Trade Duration / Expiry**: 1-Minute (`1M`)
- **Bollinger Bands 1 (BB1)**: Period = `10`, Multiplier / StdDev = `2.0`
- **Bollinger Bands 2 (BB2)**: Period = `13`, Multiplier / StdDev = `2.0`
- **Envelope Extremes**:
  - $\text{Upper Trigger} = \max(\text{Upper BB}_{10, 2},\, \text{Upper BB}_{13, 2})$
  - $\text{Lower Trigger} = \min(\text{Lower BB}_{10, 2},\, \text{Lower BB}_{13, 2})$

---

### Signal Logic & Conditions:

#### 🟢 CALL (Buy) Signal Rules:
1. **Bearish Candle**: The trigger candle must close lower than its open ($\text{Close} < \text{Open}$).
2. **Dual Lower Band Breach**: The closing price is strictly below the lowest band:
   $$\text{Close} < \text{Lower Trigger}$$
3. **20%–25% Body Protrusion**:
   $$\text{Protrusion} = \text{Lower Trigger} - \text{Close} \ge 0.20 \times (\text{Open} - \text{Close})$$
   *Crucial: Wicks alone poking past the band are rejected.*
4. **Market Structure Check**:
   - **Range/Consolidation** ($\text{ADX} < 25$): Valid immediate mean reversion entry.
   - **Trending/Wave** ($\text{ADX} \ge 25$): Valid only if the candle low tests a confirmed horizontal support zone.

#### 🔴 PUT (Sell) Signal Rules:
1. **Bullish Candle**: The trigger candle must close higher than its open ($\text{Close} > \text{Open}$).
2. **Dual Upper Band Breach**: The closing price is strictly above the highest band:
   $$\text{Close} > \text{Upper Trigger}$$
3. **20%–25% Body Protrusion**:
   $$\text{Protrusion} = \text{Close} - \text{Upper Trigger} \ge 0.20 \times (\text{Close} - \text{Open})$$
   *Crucial: Wicks alone poking past the band are rejected.*
4. **Market Structure Check**:
   - **Range/Consolidation** ($\text{ADX} < 25$): Valid immediate mean reversion entry.
   - **Trending/Wave** ($\text{ADX} \ge 25$): Valid only if the candle high tests a confirmed horizontal resistance zone.

---

## 8. Workstation Interface Tour

### 1. Header Control Bar
- **Bot Scanner Toggle**: Click `▶ START SCANNER` / `⏹ STOP SCANNER` to turn real-time market analysis on or off.
- **License Status**: Displays license validity and remaining days.
- **Quotex Status**: Real-time broker connectivity indicator.

### 2. Market Monitor (`📊 Markets`)
- Live price feed and broker payout percentage for all 27 active Forex pairs.
- Sort by Highest Payout, Asset Name, or 24h Volatility.

### 3. Canvas Candlestick Station (`📈 Chart`)
- Smooth 60 FPS hardware-accelerated charting engine.
- Toggle Candle types (Regular Candlesticks / Heikin-Ashi).
- Indicator Overlays: Dual Bollinger Bands cloud, EMA 20/50/200, MACD, RSI, and Support/Resistance lines.

### 4. Strategy Workshop (`⚙️ Strategy`)
- View and adjust mathematical parameters for the Dual Bollinger strategy.
- 18 instant Archetype presets available to inspect or customize.
- Live test simulator with historic replay.

### 5. Risk Safeguards & Circuit Breakers (`🛡️ Risk`)
- **Daily Profit Target**: Automatically stops scanner when target dollar amount or % is achieved.
- **Max Consecutive Losses**: Circuit breaker halts scanning after $N$ consecutive losses to preserve capital.
- **High-Impact News Filter**: Automatically suspends trading $\pm 15$ minutes around Tier-1 Forex news events (NFP, CPI, FOMC, Interest Rate Decisions).

---

## 9. 24/7 VPS Headless Deployment

For automated round-the-clock signal generation on a Windows or Linux Cloud VPS:

```bash
# Run in background headless mode (no GUI window launched)
python main_personal.py --headless
```

### Tips for VPS Deployment:
- Use a VPS located in London, New York, or Frankfurt for sub-15ms execution latency to Forex liquidity providers.
- Configure Windows Task Scheduler or systemd to auto-restart `main_personal.py --headless` on server reboot.

---

## 10. Troubleshooting & FAQ

### Q1: Why is the "Start Scanner" button disabled?
> **Answer**: Ensure you have logged into Quotex inside the **🏛️ Quotex Broker** tab. The scanner is gated for safety until broker authentication is complete.

### Q2: Why are there no OTC pairs visible?
> **Answer**: TradePulse Personal is strictly designed for **100% Real Interbank Forex Markets**. OTC pairs are intentionally filtered out to eliminate simulated broker spreads.

### Q3: Telegram messages are not sending.
> **Answer**:
> 1. Ensure your bot is started (send `/start` to your bot in Telegram).
> 2. Verify that the bot token and chat ID are saved correctly.
> 3. Click **Send Test Message** in the Telegram settings tab to view the exact error code if any.

### Q4: How do I backup my personal trading history and settings?
> **Answer**: All personal data is stored in your user profile:
> `C:\Users\<YourUsername>\.tradepulse\tradepulse_personal.db`
> `C:\Users\<YourUsername>\.tradepulse\strategies_personal.json`

---

*TradePulse Personal Edition — Precision Algorithmic Engineering for Modern Forex Traders.*
