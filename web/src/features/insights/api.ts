import { useQuery } from "@tanstack/react-query";

const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000").replace(/\/$/, "");

async function getJson<T>(path: string, params: Record<string, string | number | boolean | undefined> = {}): Promise<T> {
  const url = new URL(`${API_URL}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString());
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) message = String(body.detail);
    } catch {
      /* keep default message */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

/* ---------- Types ---------- */

export type MoodComponents = Partial<Record<"rsi" | "momentum" | "trend" | "volatility" | "volume", number>>;

export interface CoinMood {
  score: number;
  label: string;
  components: MoodComponents;
  change_24h_pct?: number;
  insufficient_data?: boolean;
}

export interface MarketMood {
  score: number;
  label: string;
  components: MoodComponents;
  coins: Record<string, CoinMood>;
  updated_at?: number;
}

export interface UsdInrRate {
  base: "USD";
  quote: "INR";
  rate: number;
  updated_at: number | null;
}

export interface Factor {
  key: string;
  name: string;
  value: string;
  score: number;
  effect: "bullish" | "bearish" | "neutral" | "risk";
  detail: string;
  risk?: boolean;
}

export interface Explanation {
  symbol: string;
  interval: string;
  factors: Factor[];
  net_score: number;
  leaning: "bullish" | "bearish" | "neutral";
  risk_penalty?: number;
  note?: string;
  insufficient_data?: boolean;
}

export interface QuantStrategy {
  trades: number;
  win_rate: number | null;
  win_rate_ci95: [number, number] | null;
  avg_return: number | null;
  total_return: number;
  max_drawdown: number;
  profit_factor: number | null;
  sharpe: number | null;
  sortino: number | null;
  equity: { time: number; equity: number }[];
}

export interface QuantReport {
  period_days: number;
  horizon_minutes: number;
  allow_short: boolean;
  costs: { fee_per_side_pct: number; slippage_per_side_pct: number };
  signals_considered: number;
  strategy: QuantStrategy;
  buy_and_hold: { average_total_return: number | null; by_symbol: Record<string, number | null> };
  random: { median_total_return: number; p5: number; p95: number; simulations: number } | null;
  beats_random_pct: number | null;
  verdict: string;
  notes: string[];
}

export interface QuantParams {
  days: number;
  horizonMinutes: number;
  allowShort: boolean;
  symbol?: string;
}

/* ---------- Hooks ---------- */

export function useMarketMood() {
  return useQuery({
    queryKey: ["insights", "mood"],
    queryFn: () => getJson<MarketMood>("/insights/mood"),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 2,
  });
}

export function useUsdInrRate() {
  return useQuery({
    queryKey: ["insights", "fx", "USD", "INR"],
    queryFn: () => getJson<UsdInrRate>("/insights/fx"),
    staleTime: 60 * 60_000,
    retry: 1,
  });
}

/** `at` is optional: pass a signal's time (ISO string or epoch ms) to explain a past signal. */
export function useSignalExplanation(symbol: string, interval = "5m", at?: string | number) {
  return useQuery({
    queryKey: ["insights", "explain", symbol, interval, at ?? "now"],
    queryFn: () => getJson<Explanation>("/insights/explain", { symbol, interval, at }),
    enabled: Boolean(symbol),
    refetchInterval: at ? false : 30_000,
    staleTime: at ? Infinity : 15_000,
    retry: 1,
  });
}

export function useQuantReport({ days, horizonMinutes, allowShort, symbol }: QuantParams) {
  return useQuery({
    queryKey: ["insights", "quant", days, horizonMinutes, allowShort, symbol ?? "all"],
    queryFn: () =>
      getJson<QuantReport>("/insights/quant", {
        days,
        horizon_minutes: horizonMinutes,
        allow_short: allowShort,
        symbol,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
  });
}
