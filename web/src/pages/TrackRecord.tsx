import { motion } from "framer-motion";
import { Activity, ArrowUpRight, SlidersHorizontal } from "lucide-react";
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
  const totalSamples = usable.reduce((sum, record) => sum + record.sample_count, 0);
  const totalCorrect = usable.reduce((sum, record) => sum + record.correct_count, 0);
  const overallRate = totalSamples ? (totalCorrect / totalSamples) * 100 : null;
  const settings = settingsQuery.data;
  return <motion.div className="page-stack" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <PageTitle eyebrow="PERFORMANCE" title="Track Record" subtitle="Measure outcomes over time, by market, signal type, and regime." right={<span className="period-chip"><span />60-minute outcomes</span>} />
    {trackQuery.isError && <ErrorNotice message={trackQuery.error.message} />}
    {changesQuery.isError && <ErrorNotice message={changesQuery.error.message} />}
    {settingsQuery.isError && <ErrorNotice message={settingsQuery.error.message} />}
    <div className="track-intro"><div className="intro-icon"><Activity size={19} /></div><p>A signal is counted as right when price moves more than <b>{Number.isFinite(settings?.outcome_move_threshold_pct) ? `${settings?.outcome_move_threshold_pct.toFixed(1)}%` : "—"}</b> in its predicted direction within 60 minutes. Hit rate uses mature 60-minute outcomes.</p><span className="intro-period">LIVE METRICS</span></div>
    <Panel className="track-hit-rate">
      <span className="track-hit-rate-label">OVERALL HIT RATE · {totalSamples.toLocaleString()} MATURE SIGNALS</span>
      <strong>{overallRate === null ? "—" : `${overallRate.toFixed(1)}%`}</strong>
      <HitRateBlocks rate={overallRate ?? 0} label="Overall hit rate" />
    </Panel>
    <div className="chart-grid-two"><Panel title="Hit rate by coin" subtitle="Weighted by number of mature signals" className="performance-panel"><HitRateChart data={coinData} /></Panel><Panel title="Hit rate by event type" subtitle="60-minute directional accuracy" className="performance-panel"><HitRateChart data={eventData} /></Panel></div>
    <Panel title="Regime filter impact" subtitle="Before and after regime / timeframe filtering" className="performance-panel"><HitRateChart data={compareData.map((item) => ({ ...item, name: item.name.toLowerCase().includes("legacy") ? "Before filter" : "After filter" }))} /></Panel>
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

export function HitRateChart({ data }: { data: { name: string; rate: number; samples: number }[] }) {
  return data.length ? <div className="hit-rate-list">{data.map((item, index) => <div className="hit-rate-row" key={`${item.name}-${index}`}>
    <div><b>{item.name}</b><span>{item.rate.toFixed(1)}% · {item.samples} signals</span></div>
    <HitRateBlocks rate={item.rate} label={`${item.name} hit rate`} />
  </div>)}</div> : <div className="chart-empty"><Activity size={18} /><span>Not enough mature outcomes to chart yet</span></div>;
}

function HitRateBlocks({ rate, label }: { rate: number; label: string }) {
  const filled = Math.round(Math.max(0, Math.min(100, rate)) / 5);
  return <div className={`hit-rate-blocks ${rate >= 55 ? "rate-up" : "rate-down"}`} role="img" aria-label={`${label}: ${rate.toFixed(1)} percent`}>
    {Array.from({ length: 20 }, (_, index) => <span key={index} className={index < filled ? "is-filled" : ""} />)}
  </div>;
}
