# Deployment Guide

## Quick Local Run (Zero External Dependencies)

TradePulse AI is designed to run locally out-of-the-box using the built-in SQLite async engine, mock market data feeds, and heuristic AI analysis without needing paid accounts.

### 1. Backend Startup
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
The backend will automatically initialize the database and seed the default demo user (`demo@tradepulse.ai` / `password123`) and the built-in **Pattern Type 14** strategy.

### 2. Frontend Startup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## Docker Compose Deployment

To run the complete production-style containerized stack (PostgreSQL, Redis, FastAPI Backend, React Frontend):

```bash
cp .env.example .env
docker compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API Docs: `http://localhost:8000/docs`
