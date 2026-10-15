import { useMarketMood, type MoodComponents } from "./api";
import { cardClass, mutedClass } from "./format";

const COMPONENT_LABELS: Record<keyof MoodComponents, string> = {
  rsi: "RSI",
  momentum: "24h momentum",
  trend: "Trend vs EMA 50",
  volatility: "Volatility (calm = greed)",
  volume: "Volume confirmation",
};

function moodTone(score: number) {
  return score < 40 ? "mood-down" : score >= 60 ? "mood-up" : "mood-neutral";
}

function MoodBlocks({ score, label }: { score: number; label: string }) {
  const filled = Math.round(Math.max(0, Math.min(100, score)) / 5);
  return (
    <div className={`mood-blocks ${moodTone(score)}`} role="img" aria-label={`${label}: ${Math.round(score)} out of 100`}>
      {Array.from({ length: 20 }, (_, index) => (
        <span key={index} className={index < filled ? "mood-block is-filled" : "mood-block"} />
      ))}
    </div>
  );
}

export default function MoodMeter({ className = "" }: { className?: string }) {
  const { data, isLoading, isError, error, refetch } = useMarketMood();

  return (
    <section className={`${cardClass} ${className}`} aria-labelledby="mood-title">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="mood-title" className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Market Mood
          </h2>
          <p className={`text-xs ${mutedClass}`}>Built from Vanta's own live data across all coins</p>
        </div>
        {data && (
          <span className={`mood-label ${moodTone(data.score)}`}>
            {data.label}
          </span>
        )}
      </div>

      {isLoading && <div className="mt-4 h-40 animate-pulse rounded-xl bg-zinc-200/70 dark:bg-white/5" />}

      {isError && (
        <div className={`mt-4 rounded-xl border border-dashed border-zinc-300 p-4 text-sm dark:border-white/10 ${mutedClass}`}>
          <p>Couldn't load market mood. {(error as Error)?.message}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 min-h-[44px] rounded-lg px-3 text-sm font-medium text-violet-600 hover:underline dark:text-violet-400"
          >
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <div className="mood-score">
            <strong>{Math.round(data.score)}<small>/100</small></strong>
            <MoodBlocks score={data.score} label="Market mood" />
          </div>

          <ul className="mt-3 space-y-2">
            {(Object.keys(COMPONENT_LABELS) as (keyof MoodComponents)[]).map((key) => {
              const v = data.components?.[key];
              if (v === undefined) return null;
              return (
                <li key={key} className="mood-component-row">
                  <span>{COMPONENT_LABELS[key]}</span>
                  <b className="tabular-nums">{Math.round(v)}</b>
                  <MoodBlocks score={v} label={COMPONENT_LABELS[key]} />
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(data.coins ?? {}).map(([symbol, coin]) => (
              <span
                key={symbol}
                className={`mood-coin ${moodTone(coin.score)}`}
                title={coin.insufficient_data ? "Not enough data yet" : coin.label}
              >
                <span className="font-medium text-zinc-800 dark:text-zinc-200">{symbol.replace("USDT", "")}</span>
                <span className={`tabular-nums ${mutedClass}`}>{coin.insufficient_data ? "—" : Math.round(coin.score)}</span>
                {!coin.insufficient_data && <MoodBlocks score={coin.score} label={`${symbol} mood`} />}
              </span>
            ))}
          </div>

          <p className={`mt-3 text-[11px] leading-relaxed ${mutedClass}`}>
            A sentiment gauge, not a prediction. Not financial advice.
          </p>
        </>
      )}
    </section>
  );
}
