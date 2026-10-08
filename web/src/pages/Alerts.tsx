import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Bell, Download, SlidersHorizontal, Zap } from "lucide-react";
import { api } from "../api/client";
import type { Alert } from "../api/types";
import { useApiQuery, useSignals, EmptyState, ErrorNotice, LoadingRows, PageTitle, Panel } from "../components/Shared";
import { useViewerPreferences } from "../components/ViewerPreferences";
import { AlertCard, SummaryCard } from "../components/AlertWidgets";
import { coinName, eventName, percent } from "../components/format";

export default function AlertsPage() {
  const [coin, setCoin] = useState("all");
  const [eventType, setEventType] = useState("all");
  const { preferences, updatePreferences } = useViewerPreferences();
  const [searchParams] = useSearchParams();
  const signalsQuery = useSignals();
  const alertsQuery = useApiQuery(
    ["alerts", coin === "all" ? "" : coin, eventType === "all" ? "" : eventType],
    () => api.alerts(coin === "all" ? undefined : coin, eventType === "all" ? undefined : eventType),
  );
  const alerts = (alertsQuery.data ?? []).filter((alert) => alert.confidence >= preferences.minimum_confidence);
  const events = Array.from(new Set((alertsQuery.data ?? []).map((alert) => alert.event_type)));

  useEffect(() => {
    const id = searchParams.get("alert");
    if (id) document.getElementById(`alert-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [alerts, searchParams]);

  const exportCsv = () => {
    const columns = ["time", "symbol", "event_type", "action", "confidence", "price", "stop_loss", "regime", "outcome", "hit_rate_pct", "sample_count", "explanation"];
    const csv = [columns.join(","), ...alerts.map((alert) => columns.map((column) => {
      const value = alert[column as keyof Alert] ?? "";
      return `"${String(value).replaceAll('"', '""')}"`;
    }).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "vanta-alerts.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return <motion.div className="page-stack" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <PageTitle eyebrow="SIGNAL ACTIVITY" title="Alerts" subtitle="Review signals, their context, and their evaluated outcomes." right={<button className="button button-primary" onClick={exportCsv}><Download size={15} />Export CSV</button>} />
    <div className="filter-bar">
      <label className="filter-control"><span>COIN</span><select value={coin} onChange={(event) => setCoin(event.target.value)}><option value="all">All coins</option>{(signalsQuery.data ?? []).map((signal) => <option key={signal.symbol} value={signal.symbol}>{coinName(signal.symbol)}</option>)}</select></label>
      <label className="filter-control"><span>EVENT TYPE</span><select value={eventType} onChange={(event) => setEventType(event.target.value)}><option value="all">All events</option>{events.map((event) => <option key={event} value={event}>{eventName(event)}</option>)}</select></label>
      <label className="confidence-filter"><span>MIN CONFIDENCE <b>{percent(preferences.minimum_confidence)}</b></span><input type="range" min="0" max="0.95" step="0.05" value={preferences.minimum_confidence} onChange={(event) => updatePreferences({ minimum_confidence: Number(event.target.value) })} /></label>
      <div className="filter-count"><SlidersHorizontal size={14} />{alerts.length} alerts</div>
    </div>
    {alertsQuery.isError && <ErrorNotice message={alertsQuery.error.message} />}
    <div className="alert-summary">
      <SummaryCard label="TOTAL SIGNALS" value={String(alerts.length).padStart(2, "0")} icon={<Bell size={17} />} />
      <SummaryCard label="BUY SIGNALS" value={String(alerts.filter((alert) => alert.action === "BUY").length).padStart(2, "0")} icon={<ArrowUpRight size={17} />} accent="green" />
      <SummaryCard label="SELL / AVOID" value={String(alerts.filter((alert) => alert.action === "SELL" || alert.action === "AVOID").length).padStart(2, "0")} icon={<ArrowDownRight size={17} />} accent="red" />
      <SummaryCard label="AVG CONFIDENCE" value={alerts.length ? percent(alerts.reduce((sum, alert) => sum + alert.confidence, 0) / alerts.length) : "—"} icon={<Zap size={17} />} accent="violet" />
    </div>
    <Panel title="Signal feed" subtitle="Most recent first" className="feed-panel">
      <div className="feed-list">{alertsQuery.isLoading ? <LoadingRows count={5} /> : alertsQuery.isError ? <ErrorNotice compact message={alertsQuery.error.message} /> : alerts.length ? alerts.map((alert, index) => <AlertCard key={alert.id} alert={alert} index={index} />) : <EmptyState title="No alerts match these filters" copy="Try changing the coin, event type, or confidence threshold." />}</div>
    </Panel>
  </motion.div>;
}
