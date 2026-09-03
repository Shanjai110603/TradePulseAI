# What was actually wrong, and what changed

## Root causes found

1. **`_live_mode` was set true just because a token *string* existed**, not
   because a connection actually worked. Every downstream check trusted this,
   so the bot believed it was "live" even when nothing was really connecting.
2. **`get_current_price()` silently returned a hardcoded snapshot price**
   (e.g. `"EUR/USD (OTC)": 1.08450`) whenever live data failed — this is the
   "fake data" corrupting your trade-outcome tracking.
3. **The direct hand-rolled WebSocket login to Quotex is inherently fragile**
   — it's a guessed replica of a private, undocumented protocol Quotex can
   change at any time. There was a half-built alternative (`/candles/ingest`
   + `ingest_candles()`) clearly meant to receive real data from somewhere
   else, but nothing ever called it.
4. **The Docker image never installed Playwright's actual browser binary**
   (`playwright install chromium` was missing from `Dockerfile.backend`), so
   any browser-based login has been silently failing in every containerized
   deployment (Oracle script, docker-compose) since day one.
5. **`/markets/candles/ingest` had no authentication** — anyone on the
   internet could have POSTed fabricated candles to your bot.
6. Currency auto-switching itself was **not actually broken** — the
   scheduler already loops every configured asset each cycle. It just never
   had real data to work with, so it looked frozen.

## What changed

- `app/engine/market_data/quotex_frame_parser.py` *(new)* — shared parser for
  Quotex's socket.io frame format.
- `app/engine/market_data/quotex_provider.py` — `is_live()` now reflects a
  *recent successful fetch*, not just a configured token. `get_current_price()`
  now returns `None` instead of a fabricated price when there's no real data
  — callers must treat `None` as "skip, don't act."
- `app/workers/scheduler.py` — skips a signal's lifecycle tick (instead of
  faking a result) when no live price is available; uses `provider.is_live()`.
- `app/telegram/formatter.py` — the two views that show a live price now
  render an honest "no live data" message instead of crashing on `None`.
- `app/api/markets.py` + `app/core/config.py` — `/candles/ingest` now
  requires `RELAY_API_KEY`.
- `app/relay/quotex_browser_relay.py` *(new)* — **the real fix**. A real,
  logged-in headless Chromium browser (Playwright) sits on the live Quotex
  trade page and listens to the websocket frames Quotex's own frontend
  naturally exchanges with its server. It parses genuine candles/ticks and
  pushes them to `/candles/ingest`. It also cycles through your asset list
  every ~25s so every currency pair gets real coverage — this is what
  actually makes auto-switching meaningful.
- `Dockerfile.relay` *(new)* + `docker-compose.yml` — relay now runs as its
  own container (`--with-deps chromium` actually installed this time),
  isolated from the API process so a browser crash doesn't take the bot down.

## Before you run it

1. Generate a relay secret and put it in `.env` (both root and `backend/`):
   ```
   python3 -c "import secrets; print(secrets.token_hex(24))"
   ```
   Set `RELAY_API_KEY=<that value>`.
2. Set `QUOTEX_EMAIL` / `QUOTEX_PASSWORD` in `.env` (used only for the
   relay's one-time login; after that it caches the session to
   `uploads/quotex_storage_state.json` and reuses it).
3. `docker compose up -d --build`

Watch it work:
```
docker compose logs -f relay
```
You should see `[RELAY] Logging in via ...` once, then repeating
`[RELAY] Ingested N candle(s) for <symbol>` lines as it cycles assets.

## If login or asset-switching stops working

Quotex's page markup isn't something I can verify from here (I don't have
network access to qxbroker.com to browser-test against). The selectors in
`SELECTORS = {...}` at the top of `quotex_browser_relay.py` are best-effort.
If it stops finding the login form or the asset switcher:

1. Run it locally with a visible browser: `python -m app.relay.quotex_browser_relay --headed`
2. Watch where it gets stuck, open DevTools on the real site, find the
   correct selector, and update `SELECTORS`.
3. Check `uploads/relay_debug/` — it auto-saves a screenshot every time a
   step fails, which is usually enough to spot what changed.

## Hosting recommendation (zero-cost, no credit card needed beyond what AWS already required)

You're already on AWS free tier — the fix isn't to leave AWS, it's to **stop
using Windows for this**. A Windows EC2 instance spends a big share of its
1 vCPU / 1GB RAM (t2/t3.micro) on the OS itself, leaving very little for a
headless Chromium + FastAPI + Postgres. Relaunch the *same free-tier
allowance* as **Ubuntu 22.04/24.04** instead:

1. Launch a new EC2 instance → AMI: Ubuntu Server 22.04/24.04 LTS →
   instance type `t2.micro` (or `t3.micro`, whichever your account offers
   free) — same 750-hrs/month free allowance you're already using, just a
   lighter OS.
2. Install Docker: `curl -fsSL https://get.docker.com | sudo sh`
3. Copy your project over (`git clone` or `scp`), `cd` into it.
4. `sudo docker compose up -d --build`
5. Open ports 80/443/8000 in the instance's Security Group.

Two honest caveats, since you asked for genuinely $0:
- If your AWS account was created **before July 15, 2025**, this 750 free
  hrs/month lasts your account's original 12-month window. After that,
  a t2.micro is only about **$8–9/month** — cheap, but not $0.
- Free VMs that don't ask for a card at all are essentially nonexistent for
  anything you want running 24/7 — Oracle's Always-Free VM is the closest
  thing (genuinely permanent, no ongoing cost), but their signup
  verification is notoriously strict/inconsistent for cardless signups. If
  you ever get an Oracle account approved, `deploy_oracle.sh` in this repo
  already targets it and this same docker-compose setup will run there
  unchanged. Until then, Ubuntu-on-AWS is the pragmatic $0-for-now option.

## One more thing worth doing later (not urgent)

The zip you sent includes a full `venv/` folder with Windows-compiled
binaries — safe to delete before you commit/redeploy; it doesn't run on
Linux anyway and just bloats every copy of the project. Not touched here
since it doesn't affect functionality.

## A quick honest note on the strategy itself

None of this fixes whether your trading *strategy* actually has an edge —
that's a separate question from the plumbing. Quotex-style OTC binary
options are high-risk, and getting real data flowing just means your
signals will now be evaluated against reality instead of static numbers —
it doesn't make them profitable. Worth backtesting the pattern rules against
real historical data before trusting live signals with real money.
