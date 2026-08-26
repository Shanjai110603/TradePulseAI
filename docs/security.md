# Security & Operational Guardrails

## 1. Absolute Zero-Trade-Execution Scope
TradePulse AI is strictly a **Market Research, Pattern Detection, Analysis, and Signal Notification Station**.
The system contains **no trade execution engine, broker order submission, account fund management, or automated clicker/browser automation**.

## 2. Secrets Management & Environment Isolation
- All sensitive credentials (JWT keys, database passwords, bot tokens, AI API keys) are loaded strictly through environment variables or `.env`.
- Secrets are never hard-coded into repository files.
- `.env.example` provides complete configuration placeholders.

## 3. Cryptographic Security & Authentication
- User passwords are encrypted with industry-standard bcrypt hashing.
- API endpoints are protected via JWT tokens (HMAC-SHA256).
- Telegram account linking uses cryptographically secure, randomized 6-character uppercase codes that expire in 15 minutes and can only be used once.

## 4. File Upload Sanitization
- Pattern reference images are restricted to valid image MIME types (`image/png`, `image/jpeg`, `image/webp`).
- Max upload file size is enforced (5MB).
- Uploaded files are given randomized, collision-resistant filenames and are served statically as assets only.

## 5. Untrusted AI Response Validation
- All outputs from external AI providers are validated strictly against Pydantic schemas.
- Malformed or invalid AI outputs are rejected safely and logged. AI outputs cannot bypass deterministic rule engine requirements.
