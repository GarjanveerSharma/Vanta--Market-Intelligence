import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { api } from "../api/client";
import { useApiQuery, EmptyState, ErrorNotice, PageTitle } from "../components/Shared";

export default function GuidePage() {
  const [search, setSearch] = useState("");
  const settingsQuery = useApiQuery(["calibration-settings"], api.calibrationSettings);
  const settings = settingsQuery.data;
  const outcomeThreshold = settings ? `${settings.outcome_move_threshold_pct}%` : "—";
  const calibrationMin = settings?.min_samples ?? "—";
  const sections = useMemo(() => [
    { title: "What Vanta is", text: "Vanta monitors public Binance market candles and produces rule-based crypto signals. It has no account or login and does not use an AI/LLM to generate explanations." },
    { title: "How signals are made", text: `Price, returns, RSI and volume z-score feed deterministic event rules. Pump/dump rules require a 1-hour move of at least 5% and volume z-score ≥2; breakouts need price at resistance, volume z-score ≥1 and RSI between 35 and 75; whale events require a 1-minute move of at least 1% and volume z-score ≥3; volume spikes require z-score ≥3; RSI rules flag ≤30 or ≥70. Alerts use the configured confidence threshold (${settings?.alert_confidence_threshold != null ? `${Math.round(settings.alert_confidence_threshold * 100)}%` : "—"}), subject to per-rule calibration and cooldown. Explanations are templates, not model output.` },
    { title: "Reading BUY, SELL, HOLD and AVOID", text: "BUY indicates an upward directional setup; SELL indicates a downward setup; HOLD means no clear directional majority or an observational event; AVOID marks a downward-risk event where the detector advises caution. Confidence is the detector's estimated rule score, not a probability or guarantee. Stop-loss is a reference level derived from the event and risk assumptions; it does not place an order." },
    { title: "Market regime", text: `The regime detector uses ADX(14) and ATR(14) on 15-minute candles. ADX at or above ${settings?.regime_adx_threshold ?? "—"} identifies a directional trend; positive directional movement means TRENDING_UP, otherwise TRENDING_DOWN. ATR as a percent of close at or above ${settings?.regime_high_volatility_atr_pct ?? "—"}% takes precedence and is labeled HIGH_VOLATILITY. Other markets are SIDEWAYS. In high volatility, confidence is multiplied by ${settings?.high_volatility_confidence_multiplier ?? "—"} and stop distance by ${settings?.high_volatility_stop_multiplier ?? "—"}.` },
    { title: "Timeframe agreement", text: "Signals are compared across 1m, 5m and 15m. Three matching votes are confirmed. Two of three matching votes are partial and confidence is reduced to 75% of the supporting average. Fewer than two directional votes results in HOLD. A display such as “1m ✓ 5m ✓ 15m ✗” shows the individual votes." },
    { title: "Track Record and self-calibration", text: `An outcome is correct when price moves more than ${outcomeThreshold} in the predicted direction at a 15-, 30- or 60-minute horizon. Track Record hit rates use mature 60-minute outcomes and are withheld until at least 10 samples. Daily self-calibration considers rules with at least ${calibrationMin} samples and hit rate below ${settings?.low_hit_rate_pct ?? "—"}%; changes are bounded and logged. Calibration can be switched only by an administrator with X-Admin-Key.` },
    { title: "Chart signal markers", text: "BUY markers are green triangles below candles; SELL markers are red triangles above. HOLD and AVOID are subtler markers. Use the Show signals toggle and signal-type filter. Select or tap a marker to view its confidence, regime and tracked outcome (correct, wrong or pending)." },
    { title: "Backtest metrics and limits", text: "Backtests replay stored candle history through Vanta's rule logic and summarize precision, recall, simulated equity, and event lead time. Missing or short market history can limit results. Fees, slippage, liquidity and execution are not fully represented. Historical results do not predict future performance." },
    { title: "Notifications", text: "Browser notifications, a subtle sound and in-app toasts apply only while this Vanta tab is open. Choose the minimum confidence and mute the sound in Settings. If browser notifications are blocked or unsupported, qualifying alerts remain available as in-app toasts." },
    { title: "Glossary", text: "RSI (Relative Strength Index) summarizes recent momentum; this detector flags oversold at 30 or below and overbought at 70 or above. Volume z-score measures how unusual volume is relative to its recent history. ADX measures trend strength; ATR measures typical range and volatility. Volatility describes the magnitude of price movement, not its direction." },
    { title: "FAQ", text: "Not financial advice: signals can be wrong. Data refreshes through a live WebSocket while connected, with polling fallback if the socket is unavailable. There is no account or login. Viewer preferences stay in your browser; the admin key is not saved." },
    { title: "Disclaimer", text: "Signals are automated and can be wrong. Not financial advice. Vanta does not execute trades, provide individualized investment advice, or guarantee results. Verify market data and make independent decisions." },
  ], [calibrationMin, outcomeThreshold, settings]);
  const visibleSections = sections.filter((section) =>
    `${section.title} ${section.text}`.toLowerCase().includes(search.trim().toLowerCase()));

  return <div className="page-stack guide-page">
    <PageTitle eyebrow="VANTA FIELD GUIDE" title="Guide" subtitle="Understand the signals, metrics, and controls." />
    <label className="guide-search"><Search size={17} /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search the guide" aria-label="Search the guide" /></label>
    {settingsQuery.isError && <ErrorNotice message={settingsQuery.error.message} />}
    <section className="guide-sections">{visibleSections.length ? visibleSections.map((section, index) =>
      <details className="guide-section" key={section.title} open={index === 0 && search.length === 0}>
        <summary>{section.title}<span aria-hidden="true">+</span></summary>
        <p>{section.text}</p>
      </details>) : <EmptyState title="No guide sections found" copy="Try another search phrase." />}</section>
  </div>;
}
