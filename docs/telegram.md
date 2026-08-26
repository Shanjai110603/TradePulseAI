# Telegram Bot Integration

## Overview

TradePulse AI features an interactive Telegram Bot that delivers concise signal notifications and rich callback views without spamming new messages.

## Account Linking Flow

To link a Telegram account to a Web Workstation:
1. User logs into the Web Dashboard and navigates to **Settings > Telegram**.
2. User clicks **Generate New Linking Code** (generates a secure 6-character code e.g. `ABC123` with 15-minute expiration).
3. In Telegram, the user opens `@TradePulseAIBot` and sends:
   ```text
   /link ABC123
   ```
4. The backend verifies the code, maps the user's Telegram `chat_id` and `user_id`, and activates alerts.

## Main Signal Notification Format

The initial signal alert is formatted concisely:

```text
🚨 NEW RESEARCH SIGNAL

💎 EUR/USD

🔴 DOWN

💰 Reference Price
1.08542

⏰ Entry
10:35:20

⌛ Expiry
10:40:20

⏱ Duration
5 Minutes

🔷 Pattern
Pattern Type 14

🧠 AI Score
88/100

📊 Signal Strength
HIGH

📌 Status
ACTIVE
```

## Interactive Inline Keyboards

The alert card is accompanied by 6 inline callback buttons:
- 🧠 **AI Analysis**: Renders full AI reasoning, confidence, trend, momentum, structure assessment, and risks.
- 📊 **Technicals**: Renders RSI, MACD, EMA fast/slow, Bollinger Bands, ATR, ADX, and key S/R pivots.
- 📈 **Live Signal**: Displays real-time delta between reference price and latest market tick, with profit zone indicator.
- 📋 **Full Details**: Displays full audit trails and trigger timestamps.
- 🔔 **Follow Signal**: Subscribes user to live target/expiry lifecycle updates.
- 🔕 **Mute**: Silences notifications temporarily.
