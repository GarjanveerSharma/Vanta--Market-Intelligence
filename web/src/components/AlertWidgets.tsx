import { motion } from "framer-motion";
import { Activity, ArrowDownRight, ArrowUpRight, Shield } from "lucide-react";
import type { ReactNode } from "react";
import type { Alert } from "../api/types";
import { SignalOutcome } from "./Shared";
import { coinName, eventName, money, percent } from "./format";

export function SummaryCard({ label, value, icon, accent = "" }: { label: string; value: string; icon: ReactNode; accent?: string }) {
  return <div className={`summary-card ${accent}`}><div className="summary-icon">{icon}</div><div><span>{label}</span><b>{value}</b></div></div>;
}

export function AlertCard({ alert, index }: { alert: Alert; index: number }) {
  const count = alert.sample_count ?? 0;
  const enoughData = count >= 10 && Number.isFinite(alert.hit_rate_pct);
  const track = enoughData
    ? `Right ${Math.round(alert.hit_rate_pct as number)}% of the time, ${count} signals`
    : `Not enough data yet (${count} signals; need 10)`;
  return <motion.article id={`alert-${alert.id}`} className="alert-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24, delay: Math.min(index * 0.025, 0.2) }}>
    <div className={`alert-icon-box alert-${alert.action.toLowerCase()}`}>{alert.action === "BUY" ? <ArrowUpRight size={18} /> : alert.action === "SELL" ? <ArrowDownRight size={18} /> : alert.action === "AVOID" ? <Shield size={17} /> : <Activity size={17} />}</div>
    <div className="alert-card-content">
      <div className="alert-head"><div><span className={`action-pill action-${alert.action.toLowerCase()}`}>{alert.action}</span><b>{coinName(alert.symbol)} <small>/ USDT</small></b><span className="event-chip">{eventName(alert.event_type)}</span></div><time>{new Date(alert.time).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time></div>
      <p className="alert-explanation">{alert.explanation || "—"}</p>
      <div className="alert-meta-line">
        <span>Entry <b>{money(alert.price)}</b></span>
        <span>Stop-loss <b>{money(alert.stop_loss)}</b></span>
        <span>Regime <b>{eventName(alert.regime)}</b></span>
        <span className="track-note"><Activity size={13} />{track}</span>
        <SignalOutcome alert={alert} />
      </div>
    </div>
    <div className="alert-score"><span>CONFIDENCE</span><b>{percent(alert.confidence)}</b><div><i style={{ width: `${Number.isFinite(alert.confidence) ? alert.confidence * 100 : 0}%` }} /></div></div>
  </motion.article>;
}
