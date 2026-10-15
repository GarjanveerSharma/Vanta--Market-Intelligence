<div align="center">

# Vanta


### Real-time crypto signals that measure their own accuracy

[**Live demo →**](https://vanta-market-intelligence-topaz.vercel.app/)

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-live-000000?style=flat-square)
![Deployed on Vercel + Render](https://img.shields.io/badge/deploy-Vercel%20%2B%20Render-000000?style=flat-square)

</div>

---

Most signal tools tell you **what** to do. Vanta also tells you **how often it has been right**.

It streams live Binance data for **BTC, ETH, SOL, BNB and XRP**, detects market events, turns them into BUY / SELL / HOLD / AVOID signals, and then checks every signal afterwards, so each one comes with its own track record.

## What makes it different

| | |
|---|---|
| ✅ **Self-measured accuracy** | Every signal is re-checked 15, 30 and 60 minutes later. Each alert shows its real hit rate, like *"right 61% of the time, 44 signals"*. |
| 🔧 **Self-calibration** | Rules that keep failing get stricter thresholds automatically, within safe limits, and every change is logged. |
| 🧭 **Regime-aware** | ADX and ATR classify the market as trending, sideways or high-volatility. Counter-trend signals are suppressed. |
| ⏱ **Multi-timeframe confirmation** | A signal is confirmed only when the 1m, 5m and 15m timeframes agree. |
| 📊 **Honest backtesting** | Sharpe, drawdown and win rate after fees and slippage, compared against buy-and-hold and 300 random signal sets. |
| 🔍 **Explainable** | "Why this signal?" shows which factors (RSI, momentum, trend, volume, volatility) pushed it bullish or bearish. |
| 🌡 **Market Mood Meter** | A 0–100 fear/greed gauge built from Vanta's own live data. |

No AI or paid APIs: signals are deterministic rules, so every result can be reproduced and audited.

## Tech stack

**Backend:** Python, FastAPI, SQLAlchemy (async), PostgreSQL, WebSockets, NumPy/pandas
**Frontend:** React, TypeScript, Vite, TanStack Query, TradingView Lightweight Charts
**Infra:** Render (API), Vercel (web), Docker, Prometheus

## Run locally

Requires Python 3.11+ and Node.js 20+. No API keys needed: Binance market data is public.

```bash
# Backend
cp .env.example .env
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m api.main                                   # http://localhost:8000

# Frontend (new terminal)
cd web
npm ci
npm run dev                                          # http://localhost:5173
```

Run the tests:

```bash
python -m pytest -q
cd web && npm run build
```

## Project structure

```
api/          FastAPI routes and WebSocket
ingestion/    Binance streaming with REST fallback
processing/   Candle aggregation and features
detection/    Rules, regime filter, timeframe confirmation
evaluation/   Outcome tracking, track record, calibration
insights/     Market mood, signal breakdown, quant metrics
web/          React terminal
```

## Deployment

The API runs on **Render** with a Postgres database, and the web app on **Vercel** (root directory `web`, with `VITE_API_URL` pointing to the API). See `render.yaml` and `.env.example` for configuration.

---

<div align="center">

<sub>Signals are automated and can be wrong. Vanta is a learning project, not financial advice.</sub>

</div>
