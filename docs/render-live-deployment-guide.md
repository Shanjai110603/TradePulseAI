# TradePulse AI - Live Cloud Deployment & Telegram Setup Guide

This document is a comprehensive, step-by-step guide to take **TradePulse AI** from a local codebase to **100% live online** with 24/7 background market scanning and real-time Telegram signal delivery at **$0.00 cost**.

---

## 1. Prerequisites Checklist

Before you begin, make sure you have:
1. **GitHub Account**: To host your private/public repository.
2. **Render.com Account**: Free account on [render.com](https://render.com).
3. **Telegram Bot Token**: Created via `@BotFather` on Telegram.
   - Example token: `YOUR_TELEGRAM_BOT_TOKEN`

---

## 2. Step-by-Step Deployment

```mermaid
flowchart TD
    A[Local Codebase] -->|git push| B[GitHub Repository]
    B -->|Deploy Web Service| C[Render.com Backend]
    B -->|Deploy Static Site| D[Render.com Frontend]
    C <-->|24/7 Long Polling| E[Telegram API & Bot]
    D -->|REST API| C
    E -->|Instant Signal Cards| F[Trader Telegram App]
```

---

### Step 1: Push Code to Your GitHub Repository

If you create a new GitHub repository:

1. Create a repository on [github.com/new](https://github.com/new) (e.g. `TradePulseAI`).
2. Run the following in your project terminal:

```powershell
# Set your GitHub remote repository URL
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push code to main branch
git branch -M main
git push -u origin main --force
```

---

### Step 2: Deploy the Backend on Render.com (Free Web Service)

1. Open [dashboard.render.com](https://dashboard.render.com) and log in.
2. In the top right, click **New +** $\rightarrow$ select **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your GitHub repo.
4. Fill in the exact settings below:

| Setting | Value to Enter |
| :--- | :--- |
| **Name** | `tradepulse-backend` |
| **Region** | `Singapore` (or your closest region) |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

5. Scroll down to the **Environment Variables** section, click **Add Environment Variable**, and add:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | `your_bot_token_here` | Bot token from @BotFather |
| `TELEGRAM_TEST_MODE` | `false` | Enables live Telegram message dispatching |
| `MARKET_DATA_PROVIDER` | `binance` | Live, free real-time crypto price feeds |
| `AI_PROVIDER` | `mock` | Quantitative heuristic AI scoring (free) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./tradepulse.db` | Auto-managed SQLite (or Supabase Postgres) |
| `SECRET_KEY` | `tradepulse_prod_secret_jwt_key_2026_x89` | Security key for JWT tokens |
| `ENVIRONMENT` | `production` | Production mode |

6. Click **Create Web Service**.
7. Render will build and launch your backend. Once the build finishes, copy your live backend URL from the top of the page:
   👉 `https://tradepulse-backend-xxxx.onrender.com`

---

### Step 3: Deploy the Frontend on Render.com (Free Static Site)

1. In the Render Dashboard, click **New +** $\rightarrow$ select **Static Site**.
2. Select the same GitHub repository.
3. Configure the frontend:

| Setting | Value to Enter |
| :--- | :--- |
| **Name** | `tradepulse-frontend` |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm install && npm run build` |
| **Publish Directory** | `dist` |

4. Under **Environment Variables**, add:
   - **Key**: `VITE_API_URL`
   - **Value**: `https://tradepulse-backend-xxxx.onrender.com/api/v1` *(paste your backend URL from Step 2 followed by `/api/v1`)*
5. Click **Create Static Site**.
6. Render will compile your frontend and give you your public web dashboard URL (e.g. `https://tradepulse-frontend-xxxx.onrender.com`).

---

### Step 4: Link Your Telegram Account

1. Open your live frontend URL in your browser.
2. Sign in with the seeded demo credentials:
   - **Email**: `demo@tradepulse.ai`
   - **Password**: `password123`
3. Click **Telegram Station** in the navigation sidebar (or navigate to `/settings/telegram`).
4. Click **Generate New Linking Code** $\rightarrow$ a temporary 6-character code (e.g. `K9W2B4`) will appear.
5. In your **Telegram app**, open your bot and send:
   ```text
   /link K9W2B4
   ```
6. Your bot will reply immediately:
   > *🎉 **Successfully Linked!** Your Telegram account is now connected to your TradePulse workstation.*

---

### Step 5: Verify Live Alerts

1. In the web dashboard on the **Telegram Station** page, click **Send Sample Pattern 14 Alert**.
2. You will receive an instant signal card on Telegram with 6 interactive inline buttons:
   - 🧠 **AI Analysis**: Confidence breakdown and structural reasoning.
   - 📊 **Technicals**: Multi-timeframe indicator confluence (RSI, MACD, S/R).
   - 📈 **Live Signal**: Real-time price tracking and target delta.
   - 📋 **Full Details**: Complete audit logs and entry timestamps.
   - 🔔 **Follow Signal**: Subscribes to target triggers and outcome debriefs.
   - 🔕 **Mute**: Silences notifications temporarily.
3. When live market candles match your active strategies, the background engine will automatically notify your Telegram 24/7.

---

## 3. Optional: Using a Supabase PostgreSQL Database

If you want a free cloud PostgreSQL database instead of the built-in SQLite:
1. Create a free project on [supabase.com](https://supabase.com).
2. Go to **Project Settings** $\rightarrow$ **Database** $\rightarrow$ **Connection String (URI)**.
3. Copy the URI (e.g. `postgresql://postgres.xxx:mypassword@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`).
4. Update the **`DATABASE_URL`** variable in your Render backend settings with this URI. The backend will automatically handle pooling and create all tables.

---

## 4. Troubleshooting & Verification

| Issue | Solution |
| :--- | :--- |
| Telegram bot not responding | Verify `TELEGRAM_BOT_TOKEN` in Render and ensure `TELEGRAM_TEST_MODE` is set to `false`. |
| Frontend says "Network Error" | Check that `VITE_API_URL` in the frontend static site points to `https://your-backend.onrender.com/api/v1`. |
| Code expired error | Linking codes expire after 15 minutes. Generate a fresh code in the web dashboard. |
