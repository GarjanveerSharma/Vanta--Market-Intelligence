import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CircleHelp } from "lucide-react";

import { api } from "../api/client";
import { useRealtimeStatus } from "../api/realtime";
import type { Alert } from "../api/types";

export function LiveIndicator({ live }: { live: boolean }) {
  return live ? <div className="connection-badge is-live" aria-label="Live"><span className="connection-dot" />Live</div> : null;
}

export function PageTitle({ eyebrow, title, subtitle, right }: { eyebrow: string; title: string; subtitle: string; right?: ReactNode }) {
  return <div className="page-title-row"><div><div className="eyebrow"><span />{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{right && <div className="title-actions">{right}</div>}</div>;
}

export function Panel({ children, className = "", title, subtitle, action }: { children: ReactNode; className?: string; title?: string; subtitle?: string; action?: ReactNode }) {
  return <section className={`panel ${className}`}>{(title || action) && <div className="panel-heading"><div>{title && <h2>{title}</h2>}{subtitle && <p>{subtitle}</p>}</div>{action}</div>}{children}</section>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function useApiQuery<T>(queryKey: readonly unknown[], queryFn: () => Promise<T>) {
  const realtimeStatus = useRealtimeStatus();
  return useQuery({
    queryKey,
    queryFn,
    refetchInterval: (query) =>
      query.state.status === "error" || realtimeStatus !== "connected" ? 5000 : false,
    retry: false,
  });
}

export function useSignals() {
  return useApiQuery(["signals"], api.signals);
}

export function LoadingRows({ count = 4 }: { count?: number }) {
  return <div className="loading-rows">{Array.from({ length: count }, (_, index) => <div key={index}><Skeleton /><Skeleton /><Skeleton /></div>)}</div>;
}

export function EmptyState({ title, copy }: { title: string; copy: string }) {
  return <div className="empty-state"><span><Activity size={17} /></span><b>{title}</b><p>{copy}</p></div>;
}

export function ErrorNotice({ message, compact = false }: { message: string; compact?: boolean }) {
  return <div className={`api-error ${compact ? "compact" : ""}`}><span><CircleHelp size={14} /></span><div><b>Unable to load live data</b><p>{message || "Please retry in a moment."}</p></div></div>;
}

export function SignalOutcome({ alert }: { alert: Alert }) {
  const label = alert.outcome === "correct" ? "✓ correct" : alert.outcome === "wrong" ? "✗ wrong" : "⏳ pending";
  return <span className={`outcome outcome-${alert.outcome ?? "pending"}`}>{label}</span>;
}
