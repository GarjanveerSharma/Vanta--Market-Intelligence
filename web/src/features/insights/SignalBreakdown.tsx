import { useSignalExplanation, type Factor } from "./api";
import { cardClass, mutedClass } from "./format";

interface Props {
  symbol: string;
  interval?: string;
  /** Time of a past signal (ISO string or epoch ms). Leave empty for "right now". */
  at?: string | number;
  /** Render without the card border, e.g. inside an alert card. */
  compact?: boolean;
  className?: string;
}

const EFFECT_STYLE: Record<Factor["effect"], { bar: string; text: string; label: string }> = {
  bullish: { bar: "var(--up)", text: "insight-up", label: "Bullish" },
  bearish: { bar: "var(--down)", text: "insight-down", label: "Bearish" },
  neutral: { bar: "var(--muted)", text: "insight-muted", label: "Neutral" },
  risk: { bar: "var(--down)", text: "insight-down", label: "Risk" },
};

function FactorRow({ f }: { f: Factor }) {
  const style = EFFECT_STYLE[f.effect] ?? EFFECT_STYLE.neutral;
  const width = Math.min(50, Math.abs(f.score) * 50);
  const positive = f.score >= 0;
  return (
    <li className="factor-row" title={f.detail}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="min-w-0 truncate font-medium text-zinc-800 dark:text-zinc-200">{f.name}</span>
        <span className="shrink-0 tabular-nums">
          <span className={mutedClass}>{f.value}</span>
          <span className={`ml-2 font-semibold ${style.text}`}>{style.label}</span>
        </span>
      </div>
      <div className="relative mt-1.5 h-2 rounded-full bg-zinc-200 dark:bg-white/10" aria-hidden="true">
        <span className="factor-center-line absolute left-1/2 top-[-2px] h-3 w-px bg-zinc-400 dark:bg-white/30" />
        <span
          className="absolute top-0 h-2 rounded-full transition-all duration-500"
          style={{
            backgroundColor: style.bar,
            width: `${Math.max(width, 1.5)}%`,
            left: positive ? "50%" : `${50 - width}%`,
          }}
        />
      </div>
    </li>
  );
}

export default function SignalBreakdown({ symbol, interval = "5m", at, compact = false, className = "" }: Props) {
  const { data, isLoading, isError, refetch } = useSignalExplanation(symbol, interval, at);
  const wrapper = compact ? className : `${cardClass} ${className}`;
  const coin = symbol.replace("USDT", "");

  return (
    <section className={wrapper} aria-label={`Why this signal for ${coin}`}>
      <div className="flex items-center justify-between gap-2">
        {!compact && <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Why this signal?</h3>}
        {data && !data.insufficient_data && (
          <span className={`text-xs font-semibold ${EFFECT_STYLE[data.leaning].text}`}>
            Leaning {EFFECT_STYLE[data.leaning].label.toLowerCase()}
          </span>
        )}
      </div>

      <div className={`mt-1 flex justify-between text-[10px] uppercase tracking-wide ${mutedClass}`}>
        <span>← Bearish</span>
        <span>Bullish →</span>
      </div>

      {isLoading && (
        <div className="mt-2 space-y-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-6 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
          ))}
        </div>
      )}

      {isError && (
        <p className={`mt-2 text-xs ${mutedClass}`}>
          Breakdown unavailable right now.{" "}
          <button type="button" onClick={() => refetch()} className="font-medium text-violet-600 underline dark:text-violet-400">
            Retry
          </button>
        </p>
      )}

      {data?.insufficient_data && <p className={`mt-2 text-xs ${mutedClass}`}>Not enough data yet.</p>}

      {data && !data.insufficient_data && (
        <>
          <ul className="mt-1 divide-y divide-zinc-100 dark:divide-white/5">
            {data.factors.map((f) => (
              <FactorRow key={f.key} f={f} />
            ))}
          </ul>
          {data.note && <p className={`mt-2 text-[11px] leading-relaxed ${mutedClass}`}>{data.note}</p>}
        </>
      )}
    </section>
  );
}
