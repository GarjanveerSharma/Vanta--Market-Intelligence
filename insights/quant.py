"""Risk-adjusted evaluation of Vanta's signals.

Every BUY (and optionally SELL, as a short) is turned into a trade that enters at
the open of the first candle *after* the signal and exits a fixed horizon later.
Fees and slippage are charged on both sides. Overlapping trades on the same coin
are skipped, so capital is never double-counted.
"""
from dataclasses import dataclass
from math import sqrt

import numpy as np


@dataclass
class Trade:
    symbol: str
    entry_time: int
    exit_time: int
    side: int          # +1 long, -1 short
    entry: float
    exit: float
    ret: float         # net return after costs, as a fraction


def simulate_trades(symbol: str, signals: list[tuple[int, int]], open_time: np.ndarray, opens: np.ndarray,
                    horizon_bars: int, fee: float, slippage: float, allow_short: bool = True) -> list[Trade]:
    """signals: list of (signal_time_ms, side). No look-ahead: entry is the next candle's open."""
    trades: list[Trade] = []
    if len(open_time) == 0 or horizon_bars < 1:
        return trades
    cost = 2 * (fee + slippage)
    busy_until = -1
    for t, side in sorted(signals):
        if side == -1 and not allow_short:
            continue
        i = int(np.searchsorted(open_time, t, side="right"))  # first candle opening strictly after the signal
        j = i + horizon_bars
        if i <= busy_until or j >= len(opens):
            continue
        entry, exit_ = float(opens[i]), float(opens[j])
        if entry <= 0:
            continue
        gross = side * (exit_ / entry - 1)
        trades.append(Trade(symbol, int(open_time[i]), int(open_time[j]), side, entry, exit_, gross - cost))
        busy_until = j
    return trades


def equity_curve(trades: list[Trade], start: float = 1.0) -> list[tuple[int, float]]:
    eq, points = start, []
    for tr in sorted(trades, key=lambda x: x.exit_time):
        eq *= 1 + tr.ret
        points.append((tr.exit_time, eq))
    return points


def max_drawdown(equity: list[float]) -> float:
    peak, mdd = -np.inf, 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1)
    return float(mdd)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def trade_metrics(trades: list[Trade], period_days: float) -> dict:
    n = len(trades)
    rets = np.array([t.ret for t in trades], dtype=float)
    curve = equity_curve(trades)
    eq_values = [1.0] + [v for _, v in curve]
    wins = int((rets > 0).sum())
    out = {
        "trades": n,
        "win_rate": wins / n if n else None,
        "win_rate_ci95": wilson_interval(wins, n),
        "avg_return": float(rets.mean()) if n else None,
        "total_return": eq_values[-1] - 1,
        "max_drawdown": max_drawdown(eq_values),
        "profit_factor": None,
        "sharpe": None,
        "sortino": None,
        "equity": [{"time": t, "equity": v} for t, v in curve],
    }
    gains, losses = rets[rets > 0].sum(), -rets[rets < 0].sum()
    if losses > 0:
        out["profit_factor"] = float(gains / losses)
    if n >= 2 and period_days > 0:
        per_year = sqrt(n / period_days * 365)
        sd = rets.std(ddof=1)
        if sd > 0:
            out["sharpe"] = float(rets.mean() / sd * per_year)
        downside = rets[rets < 0]
        if len(downside) >= 2 and downside.std(ddof=1) > 0:
            out["sortino"] = float(rets.mean() / downside.std(ddof=1) * per_year)
    return out


def buy_and_hold(opens: np.ndarray, fee: float, slippage: float) -> float | None:
    if len(opens) < 2 or opens[0] <= 0:
        return None
    return float(opens[-1] / opens[0] - 1 - 2 * (fee + slippage))


def random_baseline(markets: dict[str, tuple[np.ndarray, np.ndarray]], n_by_symbol: dict[str, int], long_share: float,
                    horizon_bars: int, fee: float, slippage: float, allow_short: bool,
                    sims: int = 300, seed: int = 7) -> np.ndarray:
    """Total return of random signals with the same count per coin and the same long/short mix."""
    rng = np.random.default_rng(seed)
    totals = np.empty(sims)
    for s in range(sims):
        trades: list[Trade] = []
        for sym, n in n_by_symbol.items():
            open_time, opens = markets[sym]
            usable = len(open_time) - horizon_bars - 1
            if n == 0 or usable <= 0:
                continue
            idx = np.sort(rng.choice(usable, size=min(n * 3, usable), replace=False))
            sides = np.where(rng.random(len(idx)) < long_share, 1, -1)
            sigs = [(int(open_time[i]), int(sd)) for i, sd in zip(idx, sides)]
            trades.extend(simulate_trades(sym, sigs, open_time, opens, horizon_bars, fee, slippage, allow_short)[:n])
        eq = 1.0
        for t in trades:
            eq *= 1 + t.ret
        totals[s] = eq - 1
    return totals


def verdict(n_trades: int, beats_random_pct: float | None, total_return: float) -> str:
    if n_trades < 20:
        return "Not enough trades yet to judge. Let the system run longer."
    if beats_random_pct is None:
        return "Not enough market data to compare against random signals."
    if beats_random_pct >= 95 and total_return > 0:
        return "Edge looks real: beats 95%+ of random signal sets after costs."
    if beats_random_pct >= 75:
        return "Promising: beats most random signal sets, but not yet statistically convincing."
    return "No proven edge yet: random signals do about as well after costs."
