from __future__ import annotations

import logging
import os
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from api.routes.alerts import router as alerts_router
from api.routes.backtest import router as backtest_router
from api.routes.health import router as health_router
from api.routes.signals import router as signals_router
from api.routes.track_record import router as track_record_router
from api.routes.websocket import router as websocket_router
from config.settings import get_settings
from storage.db import close_database, initialize_database
from jobs.scheduler import run_scheduler

REQUEST_COUNT = Counter("sentinel_http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("sentinel_http_request_seconds", "HTTP request latency", ["method", "path"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=get_settings().log_level)
    await initialize_database()
    workers: list[asyncio.Task[None]] = []
    if get_settings().app_env.lower() not in {"test", "testing"}:
        from ingestion.binance_ws import run as run_ingestion
        from processing.consumer import consume

        workers = [
            asyncio.create_task(consume(), name="market-processor"),
            asyncio.create_task(run_ingestion(), name="market-ingestion"),
            asyncio.create_task(run_scheduler(), name="evaluation-scheduler"),
        ]
        await asyncio.sleep(0)
    try:
        yield
    finally:
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        await close_database()


app = FastAPI(
    title="Crypto Sentinel API",
    description="Market signals, alerts, preferences, and backtest results.",
    version="1.0.0",
    lifespan=lifespan,
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(alerts_router)
app.include_router(signals_router)
app.include_router(backtest_router)
app.include_router(track_record_router)
app.include_router(websocket_router)
app.include_router(health_router)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)