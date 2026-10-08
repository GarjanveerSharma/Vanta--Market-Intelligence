# Vanta Web

Vanta Web is a responsive React terminal for real-time crypto signals. It consumes the FastAPI endpoints and `/ws` live-update stream. When the API is unreachable, it displays a waking status and then a retry action; it never shows simulated market data.

## Run locally

Start the FastAPI backend from the repository root in one terminal:

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, install and run the frontend:

```powershell
cd web
npm install
npm run dev
```

Open <http://localhost:5173>. Set `VITE_API_URL` in `web/.env.local` to point the app at another API URL (for example `VITE_API_URL=http://localhost:8000`). The API allows `http://localhost:5173` by default. Configure `ALLOWED_ORIGINS` as a comma-separated list for another browser origin. Viewer settings stay in localStorage; no login is used.

## Production build

```powershell
cd web
npm run build
npm run preview
```

The static production bundle is written to `web/dist`.

## Deploy to Vercel

1. Import this repository into Vercel and set the project root directory to `web`. The `web/vercel.json` builds and serves `dist`, and rewrites SPA routes to `index.html`.
2. If the Vercel project root is the repository root instead, the root `vercel.json` builds `web/` and serves `web/dist`; use one project root configuration, not both.
3. Add `VITE_API_URL` to the Vercel project environment variables, pointing to the deployed FastAPI API.
4. Vercel `.vercel.app` production and preview domains are allowed by the FastAPI CORS configuration. Set `ALLOWED_ORIGINS` on the API deployment to include any custom frontend domain, for example `https://vanta.example.com`.
5. Redeploy the frontend and API after updating environment variables.

The frontend is static; deploy the FastAPI backend separately. Keep the API and WebSocket endpoint reachable from the browser, configure its CORS allowlist for the deployed Vercel origin, and use HTTPS so the app can connect using `wss://`.
