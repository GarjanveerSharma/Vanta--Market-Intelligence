export const DASH = "—";

export function pct(value: number | null | undefined, digits = 1, signed = true): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const v = value * 100;
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits);
}

export function toneOf(value: number | null | undefined): "up" | "down" | "flat" {
  if (value === null || value === undefined || !Number.isFinite(value) || Math.abs(value) < 1e-9) return "flat";
  return value > 0 ? "up" : "down";
}

export const toneClass = {
  up: "insight-up",
  down: "insight-down",
  flat: "insight-muted",
} as const;

export const cardClass = "insight-card";

export const mutedClass = "insight-muted";
