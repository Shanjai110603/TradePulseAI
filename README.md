# ⚡ TradePulse AI — Institutional Binary Options & OTC Signal Station

<div align="center">

![TradePulse Banner](assets/icon.ico)

**Institutional-Grade Real-Time Signal Generation, Live Candlestick Charting, and Automated Telegram VIP Relay for Quotex OTC & Real Markets.**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Docker-brightgreen.svg)]()
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

</div>

---

## 📖 Overview

**TradePulse AI** is an advanced, automated signal intelligence and algorithmic trading workstation built for binary options markets (Quotex OTC & Real Forex/Crypto/Indices). 

Engineered with low-latency WebSocket wire decoding, native HTML5 high-performance charting, and multi-strategy confluence scoring, TradePulse delivers sub-pip institutional precision, eliminating the noise and false breakouts common in retail binary trading.

---

## 🌟 Key Features

### 1. 📡 High-Frequency Live Rate Ingestion
- **Sub-Pip Institutional Precision**: Dynamically binds decimal precision per asset directly from broker payloads (up to 5 decimal places for pairs like `EUR/USD` and 4 for high-rate pairs like `USD/INR`, `USD/PKR`, `USD/BRL`).
- **Zero-Latency WebSocket Ingester**: Real-time Socket.IO and binary frame decoders with automatic mirror failover.
- **Dynamic Asset Registry**: Automatically synchronizes live payout percentages, active asset states, and instrument catalogs.

### 2. 📊 Interactive Live Candlestick Chart Station
- **Custom Canvas Engine**: 60 FPS hardware-accelerated interactive candlestick charting with pan, zoom, crosshairs, and live price tracking.
- **Natural Candle Formation**: Zero dummy flatline fabrication; genuine Open-High-Low-Close (OHLC) aggregation with real-time countdown badges.
- **Multi-Timeframe Synthesis**: Instant on-the-fly synthesis of 1M, 3M, 5M, and 15M candle timeframes.
- **Built-in Indicators**: Real-time EMA (20/50), Dynamic Support & Resistance Pivots, Relative Strength Index (RSI 14), and Volume Histograms.
- **Tab Switch History Persistence**: Seamlessly retains continuous historical candles across navigation changes.

### 3. 🧠 Institutional Strategy Engine & Ultra Confluence
- **AST Strategy Compiler**: Dynamic rule compiler allowing complex custom multi-indicator criteria, candlestick patterns (Bullish/Bearish Engulfing, Hammer, Rejection Wicks), and momentum setups.
- **Ultra Confluence Scoring**: Detects when multiple institutional strategies align simultaneously on the same candle, upgrading setups to SSS-tier VIP signals.
- **OTC Stagnation Filter**: ATR-based volatility analysis that filters out flatline consolidation traps during illiquid OTC intervals.
- **Adaptive Timeframe Fallback**: Automatically cascades across 1M, 5M, and 15M datasets to guarantee continuous algorithmic evaluation.

### 4. 🛡️ Risk Management & Smart Execution
- **Automated Circuit Breakers**: Configurable Daily Take Profit ($ / %) and Stop Loss limits with auto-pause safety.
- **Capital Allocation Models**: Dynamic Martingale progression and expected value (EV) risk sizing calculator.
- **Economic News Blackout Guard**: Automatically silences signals during high-impact news events (CPI, NFP, FOMC) on affected currencies.

### 5. 📱 Telegram VIP Relay & Automated Reporting
- **Multi-Channel Dispatch**: Distribute signals to VIP subscriber groups and administrative channels with fine-grained event filtering.
- **Auto-Generated HD Signal Cards**: Generates instant matplotlib candlestick chart snapshots highlighting entry strikes, directions, and expiration targets.
- **Pre-Signal Alerts**: Broadcasts 15-second radar warnings before candle close so traders can prepare stakes and pairs on their broker in advance.
- **Post-Expiry Settlement**: Automatically verifies real-time exit prices upon trade expiration and reports WIN / LOSS / DRAW status with daily PnL journaling.
- **2-Way Remote Commands**: Control the bot remotely from Telegram (`/status`, `/stats`, `/pause`, `/resume`, `/bestpairs`).

---

## 🏗️ Architecture

```
TradePulseAI/
├── core/                       # Backend Core Architecture
│   ├── charts/                 # Matplotlib HD signal card chart generator
│   ├── config.py               # Pydantic environment configuration
│   ├── indicators/             # Indicator calculation engine (EMA, RSI, SMA, VWAP, ATR)
│   ├── ingester/               # WebSocket client, frame parser, asset registry
│   ├── models/                 # Candle, CandleStore, and Signal data models
│   ├── news/                   # Economic news calendar & blackout guard
│   ├── security.py             # Cryptographic session & token security
│   ├── storage/                # SQLite persistent database manager
│   ├── strategy/               # AST compiler, rules, confluence, risk manager
│   ├── telegram/               # Telegram bot bridge, formatter, template manager
│   └── webhooks/               # Local webhook server (TradingView alert receiver)
├── ui/                         # Modern Glassmorphic Desktop GUI
│   ├── app.js                  # Frontend state machine & UI controllers
│   ├── chart_widget.js         # Interactive Canvas candlestick chart engine
│   ├── index.html              # Main application dashboard layout
│   └── styles.css              # Cyberpunk dark-mode styling system
├── assets/                     # Application icons and branding assets
├── deploy/                     # Deployment scripts, Dockerfile, systemd service
├── main.py                     # Application main entrypoint
├── requirements.txt            # Python dependencies
└── .env.example                # Configuration template
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Windows 10/11, Linux, or macOS

### 1. Installation

Clone the repository:
```bash
git clone https://github.com/Shanjai110603/TradePulseAI.git
cd TradePulseAI
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure your settings:
```bash
cp .env.example .env
```

Edit `.env` to configure your Telegram bot and credentials:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_IDS=your_chat_or_channel_id
TELEGRAM_ADMIN_CHAT_IDS=your_admin_chat_id

# Quotex Connection (Optional - can be authenticated via in-app browser)
QUOTEX_EMAIL=your_email@example.com
QUOTEX_PASSWORD=your_password
```

### 3. Running the Application

Launch the desktop workstation:
```bash
python main.py
```

---

## 🛠️ Building Standalone Windows Executable

You can compile TradePulse into a single portable `.exe` using PyInstaller:

```bash
python -m PyInstaller TradePulse.spec --noconfirm
```

The resulting binaries will be available in:
- `dist/TradePulse-Standalone.exe` (Single standalone executable)
- `dist/TradePulse/TradePulse.exe` (Folder distribution)

---

## 📋 Telegram Bot Commands

When `TELEGRAM_COMMANDS_ENABLED=True`, authorized administrators can send commands directly to the Telegram bot:

| Command | Description |
| :--- | :--- |
| `/start`, `/help` | Display interactive menu and public commands |
| `/subscribe` | Subscribe to real-time VIP trade signals |
| `/unsubscribe` | Opt out of signal notifications |
| `/status` | View live system telemetry, broker latency, and active scanner state |
| `/stats` | View today's total trades, win rate, wins, losses, and strategy breakdown |
| `/bestpairs` | View top performing currency pairs sorted by win rate |
| `/pause` | Pause real-time signal generation |
| `/resume` | Resume scanner signal generation |

---

## 🔒 Security & Privacy

- **Local-First Storage**: Session tokens and trade history are stored locally in an encrypted SQLite database on your machine.
- **No Hardcoded Secrets**: All API tokens, chat IDs, and credentials are dynamically loaded from environment variables and `.env`.
- **Fail-Closed Permissions**: Administrative commands strictly reject requests from unauthorized Telegram IDs.

---

## 📄 License

Proprietary Software. Developed for algorithmic market research and institutional signal generation.
