from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from config.settings import get_settings

def interval_milliseconds(interval: str) -> int:
    units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    if len(interval) < 2 or interval[-1] not in units or not interval[:-1].isdigit():
        raise ValueError(f"Unsupported Binance kline interval: {interval}")
    return int(interval[:-1]) * units[interval[-1]]


def download_klines(symbol: str, days: int, interval: str = "1m") -> list[dict[str, Any]]:
    if days < 1 or days > 365:
        raise ValueError("days must be between 1 and 365")
    symbol = symbol.upper()
    interval_ms = interval_milliseconds(interval)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    params: dict[str, Any] = {"symbol": symbol, "interval": interval, "startTime": start_ms, "limit": 1000}
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=20) as client:
        while True:
            response = client.get(f"{get_settings().binance_rest_url}/api/v3/klines", params=params)
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            rows.extend({
                "time": datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc).isoformat(),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            } for item in batch)
            next_start = int(batch[-1][0]) + interval_ms
            if next_start <= params["startTime"] or next_start > int(time.time() * 1000):
                break
            params["startTime"] = next_start
            if len(batch) < 1000:
                break
    return rows


def save_csv(rows: list[dict[str, Any]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("time", "open", "high", "low", "close", "volume"))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public Binance OHLCV candles.")
    parser.add_argument("symbol", help="Market symbol, for example BTCUSDT")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    rows = download_klines(args.symbol, args.days, args.interval)
    output = args.output or Path("data") / f"{args.symbol.upper()}_{args.interval}.csv"
    save_csv(rows, output)
    print(f"Saved {len(rows)} candles to {output}")


if __name__ == "__main__":
    main()