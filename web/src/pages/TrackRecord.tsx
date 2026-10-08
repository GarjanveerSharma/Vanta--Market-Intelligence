import { motion } from "framer-motion";
import { Activity, ArrowUpRight, SlidersHorizontal } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { TrackRecord } from "../api/types";
import { useApiQuery, EmptyState, ErrorNotice, LoadingRows, PageTitle, Panel } from "../components/Shared";
import { coinName, eventName } from "../components/format";

export default function TrackRecordPage() {
  const trackQuery = useApiQuery(["track-record"], api.trackRecord);
  const changesQuery = useApiQuery(["calibration-changes"], api.calibrationChanges);
  const settingsQuery = useApiQuery(["calibration-settings"], api.calibrationSettings);
  const records = trackQuery.data ?? [];
  const usable = records.filter((record) => record.hit_rate_pct !== null && record.sample_count > 0);
  const coinData = groupHitRate(usable, "symbol");
  const eventData = groupHitRate(usable, "event_type");
  const compareData = groupHitRate(usable, "filter_version");
  const settings = settingsQuery.data;
  return <motion.div className="page-stack" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <PageTitle eyebrow="PERFORMANCE" title="Track Record" subtitle="Measure outcomes over time, by market, signal type, and regime." right={<span className="period-chip"><span />60-minute outcomes</span>} />
    {trackQuery.isError && <ErrorNotice message={trackQuery.error.message} />}
    {changesQuery.isError && <ErrorNotice message={changesQuery.error.message} />}
    {settingsQuery.isError && <ErrorNotice message={settingsQuery.error.message} />}
    <div className="track-intro"><div className="intro-icon"><Activity size={19} /></div><p>A signal is counted as right when price moves more than <b>{Number.isFinite(settings?.outcome_move_threshold_pct) ? `${settings?.outcome_move_threshold_pct.toFixed(1)}%` : "—"}</b> in its predicted direction within 60 minutes. Hit rate uses mature 60-minute outcomes.</p><span className="intro-period">LIVE METRICS</span></div>
    <div className="chart-grid-two"><Panel title="Hit rate by coin" subtitle="Weighted by number of mature signals" className="performance-panel"><HitRateChart data={coinData} labelKey="name" /></Panel><Panel title="Hit rate by event type" subtitle="60-minute directional accuracy" className="performance-panel"><HitRateChart data={eventData} labelKey="name" /></Panel></div>
    <Panel title="Regime filter impact" subtitle="Performance before and after timeframe / regime filtering" className="performance-panel"><HitRateChart data={compareData.map((item) => ({ ...item, name: item.name.includes("legacy") ? "Before filter" : "After filter" }))} labelKey="name" color="cyan" /></Panel>
    <Panel title="Signal breakdown" subtitle="Coin × event performance" className="breakdown-panel">{trackQuery.isLoading ? <LoadingRows count={4} /> : records.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>COIN</th><th>EVENT TYPE</th><th>REGIME</th><th>FILTER</th><th>HIT RATE</th><th>SIGNALS</th><th>CORRECT</th></tr></thead><tbody>{records.map((record, index) => <tr key={`${record.symbol}-${record.event_type}-${record.filter_version}-${index}`}><td><b>{coinName(record.symbol)}</b></td><td>{eventName(record.event_type)}</td><td><span className="soft-tag">{eventName(record.regime ?? "—")}</span></td><td><span className="soft-tag">{record.filter_version}</span></td><td>{record.enough_data && record.hit_rate_pct !== null ? <span className={record.hit_rate_pct >= 55 ? "positive" : "amber"}>{record.hit_rate_pct.toFixed(1)}%</span> : <span className="muted">Building history</span>}</td><td className="mono">{record.sample_count}</td><td className="mono">{record.correct_count}</td></tr>)}</tbody></table></div> : <EmptyState title="Building your track record" copy="Completed signal outcomes will appear once enough market history is available." />}</Panel>
    <Panel title="Calibration changes" subtitle={`Self-tuning minimum sample threshold: ${settings?.min_samples ?? "—"}`} className="calibration-panel" action={<span className={`calibration-status ${settings?.enabled ? "enabled" : ""}`}><i />{settings ? settings.enabled ? "Calibration on" : "Calibration off" : "—"}</span>}>{changesQuery.isLoading ? <LoadingRows count={2} /> : changesQuery.data?.length ? <div className="change-list">{changesQuery.data.map((change, index) => <div className="change-row" key={`${change.changed_at}-${change.event_type}-${index}`}><div className="change-status-icon"><SlidersHorizontal size={15} /></div><div className="change-details"><b>{eventName(change.event_type)} confidence updated</b><p>{change.reason}</p></div><div className="change-values"><span>{Math.round(change.old_threshold * 100)}% <ArrowUpRight size={12} /> {Math.round(change.new_threshold * 100)}%</span><small>{change.sample_count} samples · {Number.isFinite(change.hit_rate_pct) ? `${change.hit_rate_pct.toFixed(1)}%` : "—"} hit rate</small></div><time>{new Date(change.changed_at).toLocaleDateString()}</time></div>)}</div> : <EmptyState title="No calibration changes yet" copy="Automatic threshold updates will be logged here." />}</Panel>
  </motion.div>;
}

export function groupHitRate(rows: TrackRecord[], key: keyof TrackRecord) {
  const groups = new Map<string, { hits: number; samples: number }>();
  rows.forEach((row) => {
    const name = String(row[key] ?? "—");
    const current = groups.get(name) ?? { hits: 0, samples: 0 };
    current.hits += row.correct_count; current.samples += row.sample_count; groups.set(name, current);
  });
  return Array.from(groups, ([name, values]) => ({ name: eventName(name), rate: values.samples > 0 ? (values.hits / values.samples) * 100 : 0, samples: values.samples }));
}

export function HitRateChart({ data, labelKey, color = "violet" }: { data: { name: string; rate: number; samples: number }[]; labelKey: string; color?: "violet" | "cyan" }) {
  return data.length ? <div className="rechart-wrap"><ResponsiveContainer width="100%" height={250}><BarChart data={data} margin={{ top: 14, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey={labelKey} tick={{ fill: "#858599", fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis domain={[0, 100]} tick={{ fill: "#727286", fontSize: 10 }} tickFormatter={(value: number) => `${value}%`} axisLine={false} tickLine={false} /><Tooltip content={<ChartTooltip suffix="%" />} cursor={{ fill: "rgba(255,255,255,.025)" }} /><Bar dataKey="rate" name="Hit rate" radius={[5, 5, 0, 0]} maxBarSize={44}>{data.map((entry) => <Cell key={entry.name} fill={color === "cyan" ? "url(#cyanGradient)" : "url(#violetGradient)"} />)}</Bar><defs><linearGradient id="violetGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#9B7DFF" /><stop offset="100%" stopColor="#5E43C8" /></linearGradient><linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#43DBED" /><stop offset="100%" stopColor="#168FA6" /></linearGradient></defs></BarChart></ResponsiveContainer><span className="chart-footnote"><i />{data.length} groups · weighted accuracy</span></div> : <div className="chart-empty"><Activity size={18} /><span>Not enough mature outcomes to chart yet</span></div>;
}

export function ChartTooltip({ active, payload, label, suffix = "" }: { active?: boolean; payload?: { value: number; payload: { samples?: number } }[]; label?: string; suffix?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><b>{label}</b><strong>{payload[0].value.toFixed(1)}{suffix}</strong>{payload[0].payload.samples !== undefined && <span>{payload[0].payload.samples} signals</span>}</div>;
}
