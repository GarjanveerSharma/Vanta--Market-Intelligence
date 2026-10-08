import { useEffect, useSyncExternalStore } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { Alert, Candle, Signal } from "./types";

export type RealtimeStatus = "connecting" | "connected" | "disconnected";

interface MarketUpdate {
  type: "market_update";
  symbol: string;
  signal?: Signal;
  candle?: Candle;
  candles?: Partial<Record<"1m" | "5m" | "15m", Candle>>;
  alerts?: Alert[];
  outcomes?: { alert_id: number; outcome: "correct" | "wrong" | "pending" }[];
}

const listeners = new Set<() => void>();
let status: RealtimeStatus = "connecting";

function setStatus(next: RealtimeStatus): void {
  if (status === next) return;
  status = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useRealtimeStatus(): RealtimeStatus {
  return useSyncExternalStore(subscribe, () => status, () => "connecting");
}

function updateCaches(client: QueryClient, update: MarketUpdate): void {
  const signal = update.signal;
  if (signal) {
    client.setQueryData<Signal[]>(["signals"], (current) => {
      const existing = current ?? [];
      return [...existing.filter((item) => item.symbol !== update.symbol), signal];
    });
  }

  const candleUpdates = update.candles ?? (update.candle ? { "1m": update.candle } : {});
  for (const interval of ["1m", "5m", "15m"] as const) {
    const candle = candleUpdates[interval];
    if (!candle) continue;
    client.setQueryData<Candle[]>(["candles", update.symbol, interval], (current) => {
      const candles = (current ?? []).filter((item) => item.time !== candle.time);
      candles.push(candle);
      candles.sort((left, right) => Date.parse(left.time) - Date.parse(right.time));
      return candles.slice(-120);
    });
  }

  if (update.outcomes?.length) {
    const outcomes = new Map(update.outcomes.map((item) => [item.alert_id, item.outcome]));
    client.getQueryCache().findAll({ queryKey: ["alerts"] }).forEach((query) => {
      client.setQueryData<Alert[]>(query.queryKey, (current) => (current ?? []).map((alert) => {
        const outcome = outcomes.get(alert.id);
        return outcome ? { ...alert, outcome } : alert;
      }));
    });
  }

  const newAlerts = update.alerts ?? [];
  if (!newAlerts.length) return;
  client.getQueryCache().findAll({ queryKey: ["alerts"] }).forEach((query) => {
    const [, symbol, eventType] = query.queryKey as [string, string?, string?];
    const matching = newAlerts.filter((alert) =>
      (!symbol || symbol === alert.symbol) &&
      (!eventType || eventType === alert.event_type));
    if (matching.length) {
      client.setQueryData<Alert[]>(query.queryKey, (current) => {
        const existing = current ?? [];
        const ids = new Set(existing.map((alert) => alert.id));
        return [...matching.filter((alert) => !ids.has(alert.id)), ...existing].slice(0, 100);
      });
    }
  });
  window.dispatchEvent(new CustomEvent<Alert[]>("vanta:new-alerts", { detail: newAlerts }));
}

export function RealtimeBridge() {
  const client = useQueryClient();

  useEffect(() => {
    let socket: WebSocket | undefined;
    let stopped = false;
    let retryTimer = 0;
    let pingTimer = 0;
    let retryDelay = 500;

    const connect = () => {
      if (stopped) return;
      setStatus("connecting");
      const apiUrl = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
      const wsUrl = apiUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
      socket = new WebSocket(`${wsUrl}/ws`);
      socket.onopen = () => {
        retryDelay = 500;
        setStatus("connected");
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
        }, 20_000);
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as MarketUpdate | {
            type: "alert_outcome";
            symbol: string;
            outcomes: NonNullable<MarketUpdate["outcomes"]>;
          };
          if (message.type === "market_update") updateCaches(client, message);
          else updateCaches(client, { ...message, type: "market_update" });
        } catch (error) {
          console.error("Could not process a Vanta WebSocket message", error);
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        window.clearInterval(pingTimer);
        setStatus("disconnected");
        if (!stopped) {
          retryTimer = window.setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30_000);
        }
      };
    };
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      window.clearInterval(pingTimer);
      socket?.close();
    };
  }, [client]);

  return null;
}
