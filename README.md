# Vanta

Vanta is a real-time cryptocurrency signal service with a FastAPI backend and a responsive React terminal. The backend ingests public Binance candles, detects rule-based events and market regimes, records signal outcomes, and exposes its data through JSON endpoints. Explanations are deterministic templates; no LLM or paid inference service is used.

Signals are automated and can be wrong. They are not financial advice.

## Local development

Requirements: Python 3.11+, Node.js 20+, and npm.

1. Copy `.env.example` to `.env`. The defaults use SQLite and the in-process queue; no Redis account or market-data API key is needed.
2. Install Python dependencies and start the backend from the repository root:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m api.main
   ```

   The API, Binance ingestion, market processor, outcome evaluator, calibration, and cleanup scheduler run in one process. The API listens on `PORT` (or `API_PORT`, default `8000`).
3. In another terminal, start the React app:

   ```powershell
   cd web
   npm ci
   npm run dev
   ```

   Open <http://localhost:5173>. The app calls `VITE_API_URL` (defaults to `http://localhost:8000`), uses a WebSocket for live price, candle, signal and alert updates, and falls back to polling if the socket cannot connect. It never substitutes demo prices.
4. Run the backend tests and frontend production build:

   ```powershell
   python -m pytest -q
   cd web
   npm run build
   ```

To use another browser origin, set `ALLOWED_ORIGINS` to a comma-separated list of origins. Binance market data is public. If Binance's WebSocket is unavailable, ingestion polls Binance's public REST kline endpoints (including its market-data mirror) every five seconds while retrying the WebSocket. If REST endpoints are also unavailable, ingestion logs the errors and retries; API errors are not returned as fabricated backend data.

## Signal evaluation

The detector uses ADX(14) and ATR(14) on 15-minute candles to classify trends, sideways markets, and high volatility. RSI reversal signals against an established trend are suppressed. Directional confirmation uses 1m, 5m, and 15m frames: 3/3 is confirmed, 2/3 is partial with reduced confidence, and fewer matching frames produce HOLD. High volatility lowers confidence and widens stop-loss levels.

Outcomes are checked at 15, 30, and 60 minutes. A directional hit requires a price move greater than `OUTCOME_MOVE_THRESHOLD_PCT` in the predicted direction. Track-record summaries use mature 60-minute outcomes from the last 30 days and require 10 samples before showing a hit rate. Daily calibration tightens thresholds only for event types with at least `CALIBRATION_MIN_SAMPLES` outcomes and hit rate below `CALIBRATION_LOW_HIT_RATE_PCT`, bounded by `CALIBRATION_CONFIDENCE_MIN` and `CALIBRATION_CONFIDENCE_MAX`. Each change is recorded in the calibration log. Changing calibration state requires `ADMIN_API_KEY` via the `X-Admin-Key` header. Data cleanup runs daily (1m candles older than 7 days and alerts/outcomes older than 90 days).

## Deploy the API to Render with Neon

1. Create a free Neon Postgres database and copy its connection string. For SQLAlchemy async use, prefix the driver with `postgresql+asyncpg://` and retain Neon’s SSL query parameters.
2. Create a Render Blueprint from this repository and select `render.yaml`. The blueprint creates the free `vanta-api` web service, installs `requirements.txt`, starts `python -m api.main`, and checks `/health`.
3. Set the Render `DATABASE_URL` environment variable to the Neon connection string. `REDIS_URL=memory://` keeps ingestion and processing in the same web-service process. Render provides `PORT`.
4. Wait for the Render health check to pass and note the service URL, such as `https://vanta-api.onrender.com`.

The free Render service may sleep when idle, so first requests can take time while it wakes. Its local filesystem is ephemeral; Neon is required for persistent production data.

## Deploy the web app to Vercel

1. Import the repository into Vercel and set the project root directory to `web`. The root `vercel.json` builds the frontend from that directory and rewrites SPA paths to `index.html`.
2. Set Vercel’s `VITE_API_URL` to the Render API URL, for example `https://vanta-api.onrender.com`.
3. Vercel `.vercel.app` production and preview origins are allowed by the API CORS configuration. If using a custom frontend domain, set Render’s `ALLOWED_ORIGINS` to that origin, for example `https://vanta.example.com`.
4. Redeploy both services after changing environment variables.

## UptimeRobot

Create an HTTPS monitor for `https://<your-render-service>.onrender.com/health`. An HTTP(S) keyword monitor can check for `"status":"ok"`. Pinging this endpoint periodically also reduces idle sleep, subject to Render’s free-service policies.

## Optional Docker development

Copy `.env.example` to `.env`, set a local `POSTGRES_PASSWORD`, then run `docker compose up --build` to start the API, a local Postgres database, and Prometheus. The API runs the same in-process ingestion, processing, and scheduler workers as the Render service. The React frontend remains a separate Vite app in `web/`.

## Environment variables

See [`.env.example`](./.env.example) for backend configuration, tuning values, the optional admin key, frontend API URL, Docker Postgres password placeholder, and local defaults. Viewer preferences are saved only in browser localStorage. Keep real credentials in `.env` or deployment secrets; `.env` is ignored by Git.

## Project layout

- `api/`, `storage/`: FastAPI endpoints, schemas, and database persistence.
- `ingestion/`, `processing/`: Binance/news ingestion and signal processing.
- `detection/`, `advisor/`, `alerts/`: deterministic rules, regime filters, explanations, and alert evaluation.
- `evaluation/`, `jobs/`: 30-day track-record statistics, calibration, outcome tracking, and scheduled cleanup.
- `web/`: React + TypeScript UI, charts, WebSocket updates, and Vercel deployment configuration.
- `backtest/`: historical replay and metrics.
- `monitoring/`: Prometheus scrape configuration.

## Tests

```powershell
python -m pytest -q
cd web
npm run build
```
