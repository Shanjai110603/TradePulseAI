# REST API Reference

The TradePulse AI backend provides an OpenAPI 3.0 documented REST interface. Interactive Swagger UI is accessible at `http://localhost:8000/docs`.

## Endpoint Groups

### Authentication (`/api/v1/auth`)
- `POST /auth/register`: Create new trader account
- `POST /auth/login`: Authenticate and receive JWT access token
- `GET /auth/me`: Retrieve current user profile and preferences
- `PUT /auth/preferences`: Update global research filter thresholds

### Markets & Feeds (`/api/v1/markets`)
- `GET /markets`: List active market categories
- `GET /markets/{market_id}/assets`: List assets for a market
- `GET /markets/candles`: Retrieve historical OHLCV candles
- `GET /markets/data-sources`: List registered market data providers

### Pattern Management (`/api/v1/patterns`)
- `GET /patterns`: List user's patterns
- `POST /patterns`: Create new strategy pattern
- `GET /patterns/{id}`: Inspect pattern specifications and rules
- `PUT /patterns/{id}`: Update pattern and create a new version snapshot
- `POST /patterns/{id}/toggle`: Toggle pattern active/paused status
- `POST /patterns/{id}/duplicate`: Clone existing pattern
- `POST /patterns/{id}/image`: Upload visual reference image (PNG/JPG/WebP)
- `GET /patterns/{id}/versions`: View pattern revision history

### Signals (`/api/v1/signals`)
- `GET /signals`: Stream verified signals with filtering
- `GET /signals/{id}`: Deep signal research profile
- `GET /signals/{id}/technicals`: Technical indicator snapshot
- `GET /signals/{id}/analysis`: AI quantitative analysis snapshot

### Backtesting (`/api/v1/backtests`)
- `POST /backtests/run`: Execute chronological event-driven backtest
- `GET /backtests/{id}`: Retrieve backtest trade logs and equity curve
- `GET /backtests/pattern/{pattern_id}`: List previous backtest runs for pattern

### Telegram Station (`/api/v1/telegram`)
- `POST /telegram/link-code`: Generate temporary 6-character linking code
- `GET /telegram/status`: Check Telegram connection state
- `POST /telegram/webhook`: Webhook endpoint for Telegram bot updates
- `POST /telegram/test-notification`: Dispatch sample Pattern Type 14 alert card

### Performance & Telemetry (`/api/v1/performance`, `/api/v1/admin`)
- `GET /performance/overview`: Win rates, AI score correlations, asset alpha
- `GET /admin/health`: Real-time health telemetry across all subsystems
- `GET /admin/metrics`: Process memory, worker status, uptime
