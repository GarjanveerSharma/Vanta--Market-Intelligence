import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from insights import data_source as ds
from insights import routes
from insights.explain import explain
from insights.indicators import rsi
from insights.mood import coin_mood, label_for, market_mood
from insights.quant import max_drawdown, simulate_trades, trade_metrics, wilson_interval

STEP = 300_000  # 5m in ms


def make_market(n=600, drift=0.0005, seed=1, start=1_700_000_000_000):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + drift + rng.normal(0, 0.003, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    vol = rng.uniform(50, 150, n)
    t = start + np.arange(n, dtype=np.int64) * STEP
    return {"open_time": t, "open": open_, "high": high, "low": low, "close": close, "volume": vol}


# ---------- indicators ----------
def test_rsi_extremes():
    assert rsi(np.linspace(1, 2, 50)) == 100.0
    assert rsi(np.linspace(2, 1, 50)) < 1
    assert rsi([1, 2, 3]) == 50.0


# ---------- quant ----------
def test_entry_is_next_candle_no_lookahead():
    t = np.arange(10, dtype=np.int64) * STEP
    opens = np.arange(100, 110, dtype=float)
    trades = simulate_trades("X", [(int(t[2]) + 1, 1)], t, opens, 2, 0, 0)
    assert trades[0].entry_time == t[3] and trades[0].entry == 103 and trades[0].exit == 105


def test_costs_reduce_returns_and_short_flips_sign():
    t = np.arange(10, dtype=np.int64) * STEP
    opens = np.full(10, 100.0)
    opens[5] = 110
    long_ = simulate_trades("X", [(int(t[1]), 1)], t, opens, 3, 0.001, 0.0005)[0]
    assert long_.ret == pytest.approx(0.10 - 0.003)
    short = simulate_trades("X", [(int(t[1]), -1)], t, opens, 3, 0, 0)[0]
    assert short.ret == pytest.approx(-0.10)
    assert simulate_trades("X", [(int(t[1]), -1)], t, opens, 3, 0, 0, allow_short=False) == []


def test_overlapping_trades_are_skipped():
    t = np.arange(20, dtype=np.int64) * STEP
    opens = np.linspace(100, 120, 20)
    sigs = [(int(t[1]), 1), (int(t[2]), 1), (int(t[10]), 1)]
    assert len(simulate_trades("X", sigs, t, opens, 5, 0, 0)) == 2


def test_max_drawdown_and_wilson():
    assert max_drawdown([1.0, 1.2, 0.9, 1.3]) == pytest.approx(-0.25)
    lo, hi = wilson_interval(32, 50)
    assert 0.5 < lo < 0.64 < hi < 0.77
    assert wilson_interval(0, 0) is None


def test_trade_metrics_shape():
    m = make_market()
    sigs = [(int(m["open_time"][i]), 1) for i in range(0, 500, 20)]
    trades = simulate_trades("X", sigs, m["open_time"], m["open"], 12, 0.001, 0.0005)
    out = trade_metrics(trades, 2)
    assert out["trades"] == len(trades) > 10
    assert out["sharpe"] is not None and out["max_drawdown"] <= 0
    assert len(out["equity"]) == len(trades)


# ---------- mood ----------
def test_mood_rises_in_uptrend_and_falls_in_downtrend():
    up = make_market(200, drift=0.004, seed=2)
    down = make_market(200, drift=-0.004, seed=3)
    m_up = coin_mood(up["high"], up["low"], up["close"], up["volume"])
    m_down = coin_mood(down["high"], down["low"], down["close"], down["volume"])
    assert m_up["score"] > 60 > 40 > m_down["score"]
    assert all(0 <= v <= 100 for v in m_up["components"].values())


def test_mood_labels_and_aggregate():
    assert [label_for(s) for s in (5, 30, 50, 70, 95)] == ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
    agg = market_mood({"A": {"score": 70, "components": {k: 70 for k in ("rsi", "momentum", "trend", "volatility", "volume")}},
                       "B": {"score": 50, "insufficient_data": True, "components": {}}})
    assert agg["score"] == 70 and agg["label"] == "Greed"


# ---------- explain ----------
def test_explain_scores_bounded_and_leaning():
    up = make_market(200, drift=0.003, seed=4)
    out = explain(up["open"], up["high"], up["low"], up["close"], up["volume"])
    assert out["leaning"] == "bullish"
    assert all(-1 <= f["score"] <= 1 for f in out["factors"])
    assert {f["key"] for f in out["factors"]} == {"rsi", "momentum", "trend", "volume", "volatility"}
    assert explain([1], [1], [1], [1], [1])["insufficient_data"]


# ---------- routes (no network) ----------
@pytest.fixture
def client(monkeypatch):
    ds._cache.clear()
    now_ms = 1_800_000_000_000
    market = make_market(3000, drift=0.0002, seed=5, start=now_ms - 3000 * STEP)

    async def fake_klines(symbol, interval, limit=300, end_time_ms=None):
        return make_market(limit, drift=0.001, seed=hash(symbol) % 100)

    async def fake_range(symbol, interval, start_ms, end_ms):
        return market

    async def fake_alerts(symbol=None, limit=1000):
        times = market["open_time"][100:2800:60]
        return [{"symbol": "BTCUSDT", "action": "BUY" if i % 2 else "SELL",
                 "time": int(t)} for i, t in enumerate(times)] + [{"symbol": "BTCUSDT", "action": "HOLD", "time": int(times[0])}]

    monkeypatch.setattr(ds, "fetch_klines", fake_klines)
    monkeypatch.setattr(ds, "fetch_klines_range", fake_range)
    monkeypatch.setattr(ds, "fetch_alerts", fake_alerts)
    monkeypatch.setattr(routes.time, "time", lambda: now_ms / 1000)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_mood_route(client):
    r = client.get("/insights/mood")
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100 and set(body["coins"]) == set(ds.SYMBOLS)


def test_usd_inr_route_uses_live_provider(monkeypatch, client):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": "success", "rates": {"INR": 83.25}, "time_last_update_unix": 123}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url):
            assert url == "https://open.er-api.com/v6/latest/USD"
            return FakeResponse()

    monkeypatch.setattr(routes.httpx, "AsyncClient", lambda **_: FakeClient())
    response = client.get("/insights/fx")
    assert response.status_code == 200
    assert response.json() == {
        "base": "USD", "quote": "INR", "rate": 83.25, "updated_at": 123,
    }


def test_explain_route(client):
    assert client.get("/insights/explain", params={"symbol": "btcusdt"}).status_code == 200
    assert client.get("/insights/explain", params={"symbol": "DOGEUSDT"}).status_code == 400
    assert client.get("/insights/explain", params={"symbol": "BTCUSDT", "interval": "2h"}).status_code == 422


def test_quant_route(client):
    r = client.get("/insights/quant", params={"days": 30, "horizon_minutes": 60, "symbol": "BTCUSDT"})
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"]["trades"] >= 20
    assert body["random"]["simulations"] == 300
    assert 0 <= body["beats_random_pct"] <= 100
    assert body["verdict"]
    assert body["signals_considered"] == 45  # HOLD ignored
