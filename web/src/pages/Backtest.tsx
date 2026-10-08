import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Activity, Bell, ChevronDown, Shield, TrendingUp, Zap } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { Backtest as BacktestData } from "../api/types";
import { useApiQuery, ErrorNotice, PageTitle, Panel, Skeleton, useSignals } from "../components/Shared";
import { useViewerPreferences } from "../components/ViewerPreferences";
import { coinName, eventName, money, pct, percent } from "../components/format";

export default function BacktestPage() {
  const { preferences } = useViewerPreferences();
  const [symbol, setSymbol] = useState(preferences.default_coin);
  const [days, setDays] = useState(30);
  const signalsQuery = useSignals();
  const availableSymbols = Array.from(new Set([
    ...(signalsQuery.data ?? []).map((signal) => signal.symbol),
    preferences.default_coin,
  ]));
  const backtestQuery = useApiQuery(["backtest", symbol, days], () => api.backtest(symbol, days));
  const data = backtestQuery.data;
  return <motion.div className="page-stack" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <PageTitle eyebrow="HISTORICAL SIMULATION" title="Backtest" subtitle="Replay market history through the same signals to understand their edge." right={<div className="backtest-selectors"><label><span>ASSET</span><select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{availableSymbols.map((coin) => <option value={coin} key={coin}>{coinName(coin)} / USDT</option>)}</select><ChevronDown size={13} /></label><label><span>PERIOD</span><select value={days} onChange={(event) => setDays(Number(event.target.value))}>{[7, 14, 30, 60, 90].map((value) => <option key={value} value={value}>{value} days</option>)}</select><ChevronDown size={13} /></label></div>} />
    {backtestQuery.isError ? <ErrorNotice message={backtestQuery.error.message} /> : data ? <BacktestContent data={data} days={days} /> : <div className="backtest-loading">{[1, 2, 3, 4].map((key) => <Skeleton key={key} />)}</div>}
    <p className="backtest-disclaimer"><Shield size={14} />Backtests replay historical data through the same detectors. Past performance does not predict future results.</p>
  </motion.div>;
}

export function BacktestContent({ data, days }: { data: BacktestData; days: number }) {
  const equityChart = useMemo(() => data.equity.filter((_, index) => index % Math.max(1, Math.floor(data.equity.length / 80)) === 0).map((point) => ({ ...point, timeLabel: new Date(point.time).toLocaleDateString([], { month: "short", day: "numeric" }) })), [data.equity]);
  const finalEquity = data.equity.at(-1)?.equity;
  return <>
    <div className="backtest-kpis"><MetricCard label="ALERTS FIRED" value={data.total_alerts.toLocaleString()} change={`${days} day window`} icon={<Bell size={17} />} /><MetricCard label="PRECISION" value={percent(data.precision)} change="True positives / signals" icon={<TargetIcon />} accent="violet" /><MetricCard label="RECALL" value={percent(data.recall)} change="Directional moves captured" icon={<Activity size={17} />} accent="cyan" /><MetricCard label="AVG LATENCY" value={`${data.avg_latency_ms.toFixed(0)} ms`} change="From event to signal" icon={<Zap size={17} />} accent="amber" /><MetricCard label="SIMULATED P&L" value={pct(data.pnl_pct, 1)} change="Starting capital $10,000" icon={<TrendingUp size={17} />} accent={data.pnl_pct >= 0 ? "green" : "red"} /></div>
    <Panel title="Equity curve" subtitle="Simulated portfolio value over time · $10,000 starting balance" className="equity-panel"><div className="equity-highlight">{finalEquity === undefined ? "—" : money(finalEquity)}<span className={data.pnl_pct >= 0 ? "positive" : "negative"}>{pct(data.pnl_pct, 1)} total</span></div><div className="equity-chart"><ResponsiveContainer width="100%" height={300}><LineChart data={equityChart} margin={{ top: 10, right: 14, left: 4, bottom: 0 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="timeLabel" tick={{ fill: "#727286", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={40} /><YAxis domain={["auto", "auto"]} tick={{ fill: "#727286", fontSize: 10 }} tickFormatter={(value: number) => `$${(value / 1000).toFixed(1)}k`} axisLine={false} tickLine={false} width={52} /><Tooltip content={<EquityTooltip />} /><defs><linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7C5CFF" stopOpacity=".28" /><stop offset="100%" stopColor="#7C5CFF" stopOpacity="0" /></linearGradient></defs><Line type="monotone" dataKey="equity" stroke="#8B6FFF" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#22D3EE", stroke: "#0A0A12", strokeWidth: 2 }} /></LineChart></ResponsiveContainer></div></Panel>
    <div className="chart-grid-two"><Panel title="Precision by event" subtitle="Share of alerts with a correct direction" className="performance-panel"><EventBar data={data.by_event} metric="precision" format={(value) => percent(value)} color="#7C5CFF" /></Panel><Panel title="Average lead time" subtitle="Seconds before the directional move" className="performance-panel"><EventBar data={data.by_event} metric="avg_lead_seconds" format={(value) => `${value.toFixed(0)}s`} color="#22D3EE" /></Panel></div>
  </>;
}

export function TargetIcon() {
  return <span className="target-glyph">◎</span>;
}

export function MetricCard({ label, value, change, icon, accent = "" }: { label: string; value: string; change: string; icon: React.ReactNode; accent?: string }) {
  return <div className={`metric-card ${accent}`}><div className="metric-top"><span>{label}</span><i>{icon}</i></div><b>{value}</b><small>{change}</small></div>;
}

export function EquityTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><span>{label}</span><strong>{money(payload[0].value)}</strong></div>;
}

export function EventBar({ data, metric, format, color }: { data: BacktestData["by_event"]; metric: "precision" | "avg_lead_seconds"; format: (value: number) => string; color: string }) {
  return <div className="event-bars">{data.map((event) => <div className="event-bar-row" key={event.event_type}><div><span>{eventName(event.event_type)}</span><b>{format(event[metric])}</b></div><div className="event-bar-track"><i style={{ width: `${Math.max(2, Math.min(100, metric === "precision" ? event[metric] * 100 : event[metric] / 2.4))}%`, background: color }} /></div></div>)}</div>;
}
