export const money = (value: number, compact = false) =>
  Number.isFinite(value)
    ? new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: value < 1 ? 4 : value < 100 ? 2 : 0,
      notation: compact ? "compact" : "standard",
    }).format(value)
    : "—";

export const coinName = (symbol: string) => symbol.replace("USDT", "");
export const pct = (value: number, digits = 2) =>
  Number.isFinite(value) ? `${value > 0 ? "+" : ""}${value.toFixed(digits)}%` : "—";
export const percent = (value: number) => Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
export const eventName = (value?: string | null) => value ? value.replaceAll("_", " ") : "—";
export const timeLabel = (date?: string | null) =>
  date ? new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
