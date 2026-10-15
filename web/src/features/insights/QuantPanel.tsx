import { useState } from "react";
import { useQuantReport, type QuantReport } from "./api";
import { DASH, cardClass, mutedClass, num, pct, toneClass, toneOf } from "./format";

const DAY_OPTIONS = [7, 14, 30];
const HORIZON_OPTIONS = [
  { value: 15, label: "15 min" },
  { value: 60, label: "1 hour" },
  { value: 240, label: "4 hours" },
];

function Segmented<T extends number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex min-w-0 flex-col gap-1">
      <span className={`text-[11px] uppercase tracking-wide ${mutedClass}`}>{label}</span>
      <div className="inline-flex rounded-xl border border-zinc-200 p-1 dark:border-white/10">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={value === o.value}
            onClick={() => onChange(o.value)}
            className={`min-h-[40px] flex-1 whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors ${
              value === o.value
                ? "bg-violet-600 text-white"
                : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-white/5"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "up" | "down" | "flat" }) {
  return (
    <div className="min-w-0 rounded-xl border border-zinc-200 p-3 dark:border-white/10">
      <div className={`truncate text-[11px] uppercase tracking-wide ${mutedClass}`}>{label}</div>
      <div className={`mt-1 truncate text-lg font-semibold tabular-nums ${tone ? toneClass[tone] : "text-zinc-900 dark:text-zinc-100"}`}>
        {value}
      </div>
      {hint && <div className={`mt-0.5 truncate text-[11px] ${mutedClass}`}>{hint}</div>}
    </div>
  );
}

function EquityLine({ points }: { points: QuantReport["strategy"]["equity"] }) {
  if (points.length < 2) {
    return <p className={`text-xs ${mutedClass}`}>The equity curve appears once there are at least 2 trades.</p>;
  }
  const values = [1, ...points.map((p) => p.equity)];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 600;
  const H = 140;
  const xy = values.map((v, i) => [(i / (values.length - 1)) * W, H - ((v - min) / span) * (H - 12) - 6]);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const baseY = H - ((1 - min) / span) * (H - 12) - 6;
  const up = values[values.length - 1] >= 1;
  const color = up ? "var(--up)" : "var(--down)";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-32 w-full" role="img" aria-label="Equity curve after costs">
      <line x1="0" x2={W} y1={baseY} y2={baseY} strokeDasharray="4 4" className="stroke-zinc-300 dark:stroke-white/20" />
      <path d={line} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function CompareBars({ report }: { report: QuantReport }) {
  const rows = [
    { name: "Vanta signals", value: report.strategy.total_return, accent: true },
    { name: "Buy & hold", value: report.buy_and_hold.average_total_return },
    { name: "Random signals (median)", value: report.random?.median_total_return ?? null },
  ];
  const maxAbs = Math.max(0.0001, ...rows.map((r) => Math.abs(r.value ?? 0)));
  return (
    <ul className="space-y-3">
      {rows.map((r) => {
        const v = r.value;
        const w = v === null ? 0 : (Math.abs(v) / maxAbs) * 50;
        return (
          <li key={r.name}>
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className={`truncate ${r.accent ? "font-semibold text-zinc-900 dark:text-zinc-100" : mutedClass}`}>{r.name}</span>
              <span className={`tabular-nums font-medium ${toneClass[toneOf(v)]}`}>{pct(v, 2)}</span>
            </div>
            <div className="relative mt-1 h-2 rounded-full bg-zinc-200 dark:bg-white/10">
              <span className="absolute left-1/2 top-[-2px] h-3 w-px bg-zinc-400 dark:bg-white/30" />
              {v !== null && (
                <span
                  className="absolute top-0 h-2 rounded-full"
                  style={{
                    left: v >= 0 ? "50%" : `${50 - w}%`,
                    width: `${Math.max(w, 1)}%`,
                    background: v >= 0 ? "var(--up)" : "var(--down)",
                  }}
                />
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function QuantPanel({ symbol, className = "" }: { symbol?: string; className?: string }) {
  const [days, setDays] = useState(7);
  const [horizon, setHorizon] = useState(60);
  const [allowShort, setAllowShort] = useState(true);
  const { data, isLoading, isError, error, refetch, isFetching } = useQuantReport({
    days,
    horizonMinutes: horizon,
    allowShort,
    symbol,
  });
  const s = data?.strategy;
  const ci = s?.win_rate_ci95;

  return (
    <section className={`${cardClass} ${className}`} aria-labelledby="quant-title">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="quant-title" className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Risk-adjusted performance
          </h2>
          <p className={`text-xs ${mutedClass}`}>
            Every BUY/SELL signal traded with fees and slippage, compared with buy &amp; hold and random signals
          </p>
        </div>
        {isFetching && !isLoading && <span className={`text-xs ${mutedClass}`}>Updating…</span>}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-[auto_auto_1fr] sm:items-end">
        <Segmented label="Period" value={days} options={DAY_OPTIONS.map((d) => ({ value: d, label: `${d}d` }))} onChange={setDays} />
        <Segmented label="Hold each trade" value={horizon} options={HORIZON_OPTIONS} onChange={setHorizon} />
        <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-zinc-700 dark:text-zinc-200 sm:justify-end">
          <input
            type="checkbox"
            checked={allowShort}
            onChange={(e) => setAllowShort(e.target.checked)}
            className="h-4 w-4 accent-violet-600"
          />
          Count SELL signals as shorts
        </label>
      </div>

      {isLoading && (
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-zinc-200/70 dark:bg-white/5" />
          ))}
        </div>
      )}

      {isError && (
        <div className={`mt-4 rounded-xl border border-dashed border-zinc-300 p-4 text-sm dark:border-white/10 ${mutedClass}`}>
          <p>Couldn't load performance. {(error as Error)?.message}</p>
          <button type="button" onClick={() => refetch()} className="mt-2 min-h-[44px] font-medium text-violet-600 hover:underline dark:text-violet-400">
            Retry
          </button>
        </div>
      )}

      {data && s && (
        <>
          <div className="mt-4 rounded-xl border border-violet-500/30 bg-violet-500/5 p-3 text-sm text-zinc-800 dark:text-zinc-200">
            <span className="font-semibold">Verdict: </span>
            {data.verdict}
            {data.beats_random_pct !== null && (
              <span className={`block text-xs ${mutedClass}`}>
                Beats {Math.round(data.beats_random_pct)}% of {data.random?.simulations ?? ""} random signal sets.
              </span>
            )}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Kpi label="Trades" value={String(s.trades)} hint={`${data.signals_considered} signals considered`} />
            <Kpi
              label="Win rate"
              value={pct(s.win_rate, 0, false)}
              hint={ci ? `95% CI ${pct(ci[0], 0, false)} to ${pct(ci[1], 0, false)}` : undefined}
            />
            <Kpi label="Total return" value={pct(s.total_return, 2)} tone={toneOf(s.total_return)} hint="after costs" />
            <Kpi label="Sharpe" value={num(s.sharpe)} hint={s.sortino !== null ? `Sortino ${num(s.sortino)}` : "annualised"} />
            <Kpi label="Max drawdown" value={pct(s.max_drawdown, 2)} tone={s.max_drawdown < 0 ? "down" : "flat"} />
            <Kpi label="Profit factor" value={num(s.profit_factor)} hint="gains ÷ losses" />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div className="min-w-0">
              <h3 className="mb-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Equity after costs</h3>
              <EquityLine points={s.equity} />
            </div>
            <div className="min-w-0">
              <h3 className="mb-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Compared with</h3>
              <CompareBars report={data} />
              {data.random && (
                <p className={`mt-2 text-[11px] ${mutedClass}`}>
                  Random range (5th to 95th percentile): {pct(data.random.p5, 2)} to {pct(data.random.p95, 2)}
                </p>
              )}
            </div>
          </div>

          <details className="mt-4 text-xs">
            <summary className={`cursor-pointer select-none py-2 ${mutedClass}`}>
              How this is calculated (fees {data.costs.fee_per_side_pct}% + slippage {data.costs.slippage_per_side_pct}% per side)
            </summary>
            <ul className={`ml-4 list-disc space-y-1 ${mutedClass}`}>
              {data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </details>
        </>
      )}

      {data && !s && <p className={`mt-4 text-sm ${mutedClass}`}>{DASH}</p>}
    </section>
  );
}
