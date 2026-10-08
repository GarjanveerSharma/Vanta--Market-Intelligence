import type { Alert, Backtest, CalibrationChange, CalibrationSettings, Candle, Signal, TrackRecord } from "./types";

const baseUrl = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

async function request<T>(
  path: string,
  params?: Record<string, string | number>,
  init?: RequestInit,
): Promise<T> {
  const query = params
    ? `?${new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)]))}`
    : "";
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}${query}`, {
      ...init,
      signal: AbortSignal.timeout(5000),
    });
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "The server could not be reached");
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`API ${response.status}: ${detail || response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  signals: () => request<Signal[]>("/signals/latest"),
  candles: (symbol: string, interval: string) =>
    request<Candle[]>("/signals/candles", { symbol, interval, limit: 120 }),
  alerts: (symbol?: string, eventType?: string) => {
    const params: Record<string, string | number> = { limit: 100 };
    if (symbol) params.symbol = symbol;
    if (eventType) params.event_type = eventType;
    return request<Alert[]>("/alerts", params);
  },
  backtest: (symbol: string, days: number) =>
    request<Backtest>("/backtest/results", { symbol, days }),
  trackRecord: () => request<TrackRecord[]>("/track-record"),
  calibrationChanges: () => request<CalibrationChange[]>("/calibration/log", { limit: 100 }),
  calibrationSettings: () => request<CalibrationSettings>("/track-record/settings"),
  updateCalibrationEnabled: (enabled: boolean, adminKey: string) =>
    request<CalibrationSettings>("/track-record/settings", undefined, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Key": adminKey,
      },
      body: JSON.stringify({ enabled }),
    }),
};
