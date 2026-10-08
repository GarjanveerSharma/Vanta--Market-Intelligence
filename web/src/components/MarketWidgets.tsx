import { useEffect, useRef, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Check, Shield, X } from "lucide-react";
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import type { Alert, Candle, Signal } from "../api/types";
import { EmptyState, LoadingRows, Panel, SignalOutcome, Skeleton } from "./Shared";
import { coinName, eventName, money, pct, percent, timeLabel } from "./format";

export function TickerStrip({ signals, active, onSelect }: { signals: Signal[]; active: string; onSelect: (symbol: string) => void }) {
  const lastPrices = useRef<Record<string, number>>({});
  const [flashes, setFlashes] = useState<Record<string, "up" | "down">>({});
  useEffect(() => {
    const nextFlashes: Record<string, "up" | "down"> = {};
    signals.forEach((signal) => {
      const previous = lastPrices.current[signal.symbol];
      if (previous !== undefined && signal.price !== previous) nextFlashes[signal.symbol] = signal.price > previous ? "up" : "down";
      lastPrices.current[signal.symbol] = signal.price;
    });
    if (Object.keys(nextFlashes).length) {
      setFlashes(nextFlashes);
      const timeout = window.setTimeout(() => setFlashes({}), 900);
      return () => window.clearTimeout(timeout);
    }
  }, [signals]);
  if (!signals.length) return <div className="ticker-strip"><EmptyState title="Waiting for live prices" copy="Market values appear here when the server sends real data." /></div>;
  return <div className="ticker-strip">{signals.map((signal) => <button key={signal.symbol} className={`ticker-item ${active === signal.symbol ? "ticker-active" : ""} ${flashes[signal.symbol] ? `ticker-flash-${flashes[signal.symbol]}` : ""}`} onClick={() => onSelect(signal.symbol)}>
    <div className="ticker-coin"><span className={`tiny-coin coin-${coinName(signal.symbol).toLowerCase()}`}>{coinName(signal.symbol).slice(0, 1)}</span><b>{coinName(signal.symbol)}</b><small>/ USDT</small></div><strong className="mono">{money(signal.price)}</strong><span className={`ticker-change ${signal.change_1h >= 0 ? "positive" : "negative"}`}>{signal.change_1h >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{pct(signal.change_1h)}</span>
  </button>)}</div>;
}

export function CandlestickChart({ candles, signal, interval, alerts, markersEnabled }: { candles: Candle[]; signal?: Signal; interval: "1m" | "5m" | "15m"; alerts: Alert[]; markersEnabled: boolean }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const volumeRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const charts = useRef<{
    price?: IChartApi;
    volume?: IChartApi;
    rsi?: IChartApi;
    candles?: ISeriesApi<"Candlestick">;
    volumes?: ISeriesApi<"Histogram">;
    rsiLine?: ISeriesApi<"Line">;
  }>({});
  const chartHasData = useRef(false);
  const [selectedMarker, setSelectedMarker] = useState<Alert | null>(null);

  useEffect(() => {
    if (!priceRef.current || !volumeRef.current || !rsiRef.current) return;
    const isLight = document.documentElement.dataset.theme === "light";
    const options = (height: number) => ({
      width: priceRef.current!.clientWidth, height,
      layout: { background: { color: "transparent" }, textColor: isLight ? "#626277" : "#727286", fontFamily: "Inter, sans-serif", fontSize: 10 },
      grid: { vertLines: { color: isLight ? "rgba(25,25,45,.055)" : "rgba(255,255,255,.035)" }, horzLines: { color: isLight ? "rgba(25,25,45,.07)" : "rgba(255,255,255,.045)" } },
      rightPriceScale: { borderColor: isLight ? "rgba(25,25,45,.14)" : "rgba(255,255,255,.08)" },
      timeScale: { borderColor: isLight ? "rgba(25,25,45,.14)" : "rgba(255,255,255,.08)", timeVisible: true, secondsVisible: false, visible: false },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: "rgba(124,92,255,.4)", labelBackgroundColor: "#7C5CFF" }, horzLine: { color: "rgba(124,92,255,.4)", labelBackgroundColor: "#7C5CFF" } },
    });
    const priceChart = createChart(priceRef.current, options(310));
    const candleSeries = priceChart.addCandlestickSeries({
      upColor: "#22C993", downColor: "#F06477", borderUpColor: "#22C993", borderDownColor: "#F06477", wickUpColor: "#22C993", wickDownColor: "#F06477",
    });
    const volumeChart = createChart(volumeRef.current, { ...options(76), timeScale: { ...options(76).timeScale, visible: false }, rightPriceScale: { ...options(76).rightPriceScale, scaleMargins: { top: 0.08, bottom: 0 } } });
    const volumeSeries = volumeChart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "", lastValueVisible: false, priceLineVisible: false });
    const rsiChart = createChart(rsiRef.current, { ...options(94), timeScale: { ...options(94).timeScale, visible: true }, rightPriceScale: { ...options(94).rightPriceScale, scaleMargins: { top: 0.12, bottom: 0.12 } } });
    const rsiSeries = rsiChart.addLineSeries({ color: "#9C83FF", lineWidth: 2, lastValueVisible: true, priceLineVisible: false, crosshairMarkerVisible: true });
    [30, 70].forEach((level) => rsiSeries.createPriceLine({ price: level, color: "rgba(255,255,255,.13)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "" }));
    charts.current = { price: priceChart, volume: volumeChart, rsi: rsiChart, candles: candleSeries, volumes: volumeSeries, rsiLine: rsiSeries };
    let synchronizing = false;
    const syncCharts = (source: IChartApi, target: IChartApi) => source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (!range || synchronizing) return;
      synchronizing = true;
      target.timeScale().setVisibleLogicalRange(range);
      synchronizing = false;
    });
    syncCharts(priceChart, volumeChart); syncCharts(priceChart, rsiChart);
    const resizeObserver = new ResizeObserver(() => {
      const width = priceRef.current?.clientWidth ?? 0;
      if (width > 0) [priceChart, volumeChart, rsiChart].forEach((chart) => chart.applyOptions({ width }));
    });
    resizeObserver.observe(priceRef.current);
    const resize = () => {
      const width = priceRef.current?.clientWidth ?? 0;
      if (width > 0) [priceChart, volumeChart, rsiChart].forEach((chart) => chart.applyOptions({ width }));
    };
    window.addEventListener("orientationchange", resize);
    const themeObserver = new MutationObserver(() => {
      const light = document.documentElement.dataset.theme === "light";
      [priceChart, volumeChart, rsiChart].forEach((chart) => chart.applyOptions({
        layout: { textColor: light ? "#626277" : "#727286" },
        grid: { vertLines: { color: light ? "rgba(25,25,45,.055)" : "rgba(255,255,255,.035)" }, horzLines: { color: light ? "rgba(25,25,45,.07)" : "rgba(255,255,255,.045)" } },
      }));
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { resizeObserver.disconnect(); themeObserver.disconnect(); window.removeEventListener("orientationchange", resize); priceChart.remove(); volumeChart.remove(); rsiChart.remove(); charts.current = {}; };
  }, []);

  useEffect(() => {
    const { price, volume, rsi, candles: candleSeries, volumes: volumeSeries, rsiLine } = charts.current;
    if (!candles.length || !price || !volume || !rsi || !candleSeries || !volumeSeries || !rsiLine) return;
    candleSeries.setData(candles.map((candle) => ({
      time: Math.floor(new Date(candle.time).getTime() / 1000) as UTCTimestamp,
      open: candle.open, high: candle.high, low: candle.low, close: candle.close,
    })));
    volumeSeries.setData(candles.map((candle) => ({
      time: Math.floor(new Date(candle.time).getTime() / 1000) as UTCTimestamp,
      value: candle.volume,
      color: candle.close >= candle.open ? "rgba(34,201,147,.38)" : "rgba(240,100,119,.38)",
    })));
    let averageGain = 0; let averageLoss = 0;
    const rsiData = candles.map((candle, index) => {
      const change = index === 0 ? 0 : candle.close - candles[index - 1].close;
      const gain = Math.max(change, 0); const loss = Math.max(-change, 0);
      if (index < 14) { averageGain += gain / 14; averageLoss += loss / 14; }
      else { averageGain = (averageGain * 13 + gain) / 14; averageLoss = (averageLoss * 13 + loss) / 14; }
      const value = index === 0 ? signal?.rsi ?? 50 : averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
      return { time: Math.floor(new Date(candle.time).getTime() / 1000) as UTCTimestamp, value };
    });
    rsiLine.setData(rsiData);
    if (!chartHasData.current) {
      price.timeScale().fitContent();
      volume.timeScale().fitContent();
      rsi.timeScale().fitContent();
      chartHasData.current = true;
    }
  }, [candles, signal?.rsi]);

  useEffect(() => {
    const candleSeries = charts.current.candles;
    const chart = charts.current.price;
    if (!candleSeries || !chart) return;
    const intervalSeconds = Number.parseInt(interval, 10) * 60;
    const indexed = alerts.flatMap((alert) => {
      const time = Math.floor(new Date(alert.time).getTime() / 1000);
      const candleTime = candles.reduce((nearest, candle) => {
        const candidate = Math.floor(new Date(candle.time).getTime() / 1000);
        return Math.abs(candidate - time) < Math.abs(nearest - time) ? candidate : nearest;
      }, Math.floor(new Date(candles[0]?.time ?? alert.time).getTime() / 1000));
      return Math.abs(candleTime - time) <= intervalSeconds
        ? [{ alert, time: candleTime as UTCTimestamp }]
        : [];
    });
    candleSeries.setMarkers(markersEnabled ? indexed.map(({ alert, time }) => ({
      time,
      position: alert.action === "BUY" ? "belowBar" as const : "aboveBar" as const,
      color: alert.action === "BUY" ? "#22c993" : alert.action === "SELL" ? "#f07182" : alert.action === "AVOID" ? "#e8ad59" : "#9292a5",
      shape: alert.action === "BUY" ? "arrowUp" as const : alert.action === "SELL" ? "arrowDown" as const : "circle" as const,
      text: `${alert.action} ${percent(alert.confidence)}`,
    })) : []);
    const selectAtTime = (timestamp: number | undefined) => {
      if (timestamp === undefined) return;
      const match = indexed.find(({ time }) => time === timestamp);
      setSelectedMarker(match?.alert ?? null);
    };
    const onClick = (param: { time?: number | string | object }) =>
      selectAtTime(typeof param.time === "number" ? param.time : undefined);
    chart.subscribeClick(onClick);
    const onHover = (param: { time?: number | string | object }) =>
      selectAtTime(typeof param.time === "number" ? param.time : undefined);
    chart.subscribeCrosshairMove(onHover);
    return () => {
      chart.unsubscribeClick(onClick);
      chart.unsubscribeCrosshairMove(onHover);
    };
  }, [alerts, candles, interval, markersEnabled]);

  return <div className="chart-stack">
    <div className="chart-price" ref={priceRef} />
    <div className="chart-subpane chart-volume-pane"><span className="chart-label">VOL</span><div ref={volumeRef} /></div>
    <div className="chart-subpane chart-rsi-pane"><span className="chart-label">RSI 14</span><div ref={rsiRef} /></div>
    {selectedMarker && <div className="marker-details">
      <b>{selectedMarker.action} · {percent(selectedMarker.confidence)}</b>
      <span>{eventName(selectedMarker.regime)}</span>
      <SignalOutcome alert={selectedMarker} />
      <button className="text-button" onClick={() => setSelectedMarker(null)}>Close</button>
    </div>}
  </div>;
}

export function SignalCard({ signal, loading }: { signal?: Signal; loading: boolean }) {
  if (!signal && loading) return <Panel className="signal-card"><Skeleton className="signal-skel-title" /><Skeleton className="signal-skel" /><Skeleton className="signal-skel" /></Panel>;
  if (!signal) return <Panel className="signal-card"><EmptyState title="Signal unavailable" copy="Waiting for live market data." /></Panel>;
  const agreement = signal.timeframe_agreement ?? {};
  const frames = ["1m", "5m", "15m"];
  return <Panel className="signal-card">
    <div className="signal-card-top"><div className="card-kicker"><span className="pulse-violet" /> CURRENT SIGNAL</div><span className="signal-quality">{signal.signal_quality ?? "—"}</span></div>
    <div className="signal-main"><span className={`action-pill action-${signal.signal.toLowerCase()}`}>{signal.signal}</span><span className="signal-confidence">{percent(signal.confidence)} <small>confidence</small></span></div>
    <div className="confidence-track"><span style={{ width: `${signal.confidence * 100}%` }} /></div>
    <div className="signal-stats"><div><span>RSI (14)</span><b className={signal.rsi > 70 ? "negative" : signal.rsi < 30 ? "positive" : ""}>{signal.rsi.toFixed(1)}</b><div className="mini-progress"><i style={{ left: `${signal.rsi}%` }} /></div></div><div><span>Volume Z-score</span><b>{signal.volume_z > 0 ? "+" : ""}{signal.volume_z.toFixed(2)}<small>σ</small></b><small className={signal.volume_z > 2 ? "amber" : "muted"}>{signal.volume_z > 2 ? "Elevated" : "Normal range"}</small></div></div>
    <div className="signal-regime"><span>MARKET REGIME</span><span className={signal.regime ? `regime-badge regime-${signal.regime.toLowerCase()}` : "regime-badge"}>{eventName(signal.regime)}</span></div>
    <div className="agreement-row"><div className="agreement-label">TIMEFRAME AGREEMENT <span>?</span></div><div className="agreement-list">{frames.map((frame) => <span key={frame} className={agreement[frame] === undefined ? "frame-missing" : agreement[frame] ? "frame-yes" : "frame-no"}>{frame} {agreement[frame] === undefined ? "—" : agreement[frame] ? <Check size={11} /> : <X size={11} />}</span>)}</div></div>
    <div className="signal-note"><Shield size={14} /> Signals are filtered by market regime and timeframe alignment.</div>
  </Panel>;
}

export function WatchlistTable({ signals, loading, onSelect, active }: { signals: Signal[]; loading: boolean; onSelect: (symbol: string) => void; active: string }) {
  if (loading && !signals.length) return <LoadingRows count={3} />;
  return <div className="table-scroll"><table className="data-table watchlist-table"><thead><tr><th>ASSET</th><th>PRICE</th><th>1H CHANGE</th><th>RSI</th><th>VOLUME Z</th><th>SIGNAL</th></tr></thead><tbody>{signals.map((signal) => <tr key={signal.symbol} className={active === signal.symbol ? "row-active" : ""} onClick={() => onSelect(signal.symbol)}><td><div className="table-coin"><span className={`tiny-coin coin-${coinName(signal.symbol).toLowerCase()}`}>{coinName(signal.symbol).slice(0, 1)}</span><b>{coinName(signal.symbol)}</b><small>USDT</small></div></td><td className="mono">{money(signal.price)}</td><td className={`mono ${signal.change_1h >= 0 ? "positive" : "negative"}`}>{pct(signal.change_1h)}</td><td><span className={`rsi-chip ${signal.rsi > 70 ? "rsi-hot" : signal.rsi < 30 ? "rsi-cool" : ""}`}>{signal.rsi.toFixed(0)}</span></td><td className="mono">{signal.volume_z.toFixed(2)}σ</td><td><span className={`table-action action-${signal.signal.toLowerCase()}`}>{signal.signal}</span></td></tr>)}</tbody></table>{signals.length === 0 && <EmptyState title="No watchlist assets" copy="Add coins in Settings to keep an eye on them." />}</div>;
}

export function MiniAlert({ alert }: { alert: Alert }) {
  return <div className="mini-alert"><div className="mini-alert-marker"><span className={`marker-${alert.action.toLowerCase()}`} /></div><div className="mini-alert-body"><div><b>{coinName(alert.symbol)}</b><span className={`table-action action-${alert.action.toLowerCase()}`}>{alert.action}</span></div><p>{eventName(alert.event_type)} <span>·</span> {timeLabel(alert.time)}</p></div><strong className="mini-alert-confidence">{percent(alert.confidence)}</strong></div>;
}
