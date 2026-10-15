import { useEffect, useRef, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Check, Shield, X } from "lucide-react";
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type Time, type UTCTimestamp } from "lightweight-charts";
import type { Alert, Candle, Signal } from "../api/types";
import { EmptyState, LoadingRows, Panel, SignalOutcome, Skeleton } from "./Shared";
import { coinName, eventName, money, pct, percent, timeLabel } from "./format";
import { SignalBreakdown } from "../features/insights";

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
    <div className="ticker-coin"><span className={`tiny-coin coin-${coinName(signal.symbol).toLowerCase()}`}>{coinName(signal.symbol)}</span><b>{coinName(signal.symbol)}</b><small>/ USDT</small></div><strong className="mono">{money(signal.price)}</strong><span className={`ticker-change ${signal.change_1h >= 0 ? "positive" : "negative"}`}>{signal.change_1h >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{pct(signal.change_1h)}</span>
  </button>)}</div>;
}

export function CandlestickChart({ candles, signal, symbol, interval, alerts, markersEnabled }: { candles: Candle[]; signal?: Signal; symbol: string; interval: "1m" | "5m" | "15m"; alerts: Alert[]; markersEnabled: boolean }) {
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
  const chartDataKey = useRef<string | undefined>(undefined);
  const intervalRef = useRef(interval);
  intervalRef.current = interval;
  const [selectedMarkers, setSelectedMarkers] = useState<Alert[]>([]);
  const [markerTargets, setMarkerTargets] = useState<{ time: number; x: number; y: number; alerts: Alert[] }[]>([]);

  useEffect(() => {
    if (!priceRef.current || !volumeRef.current || !rsiRef.current) return;
    const isLight = document.documentElement.dataset.theme === "light";
    const upColor = isLight ? "#0C9F6A" : "#22E39A";
    const downColor = isLight ? "#E5354A" : "#FF4D5E";
    const timeScaleOptions = {
      tickMarkFormatter: (time: Time) => {
        const date = typeof time === "number"
          ? new Date(time * 1000)
          : typeof time === "string"
            ? new Date(time)
            : new Date(Date.UTC(time.year, time.month - 1, time.day));
        return intervalRef.current === "15m"
          ? date.toLocaleDateString([], { month: "short", day: "numeric" })
          : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      },
    };
    const options = (height: number) => ({
      width: priceRef.current!.clientWidth, height,
      layout: { background: { color: "transparent" }, textColor: isLight ? "#6B6B6B" : "#8A8A8A", fontFamily: "Space Grotesk, sans-serif", fontSize: 10 },
      localization: { timeFormatter: (time: Time) => {
        const date = typeof time === "number"
          ? new Date(time * 1000)
          : typeof time === "string"
            ? new Date(time)
            : new Date(Date.UTC(time.year, time.month - 1, time.day));
        return intervalRef.current === "15m"
          ? date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
          : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      } },
      grid: { vertLines: { color: isLight ? "#E4E4E4" : "#232323" }, horzLines: { color: isLight ? "#E4E4E4" : "#232323" } },
      rightPriceScale: { borderColor: isLight ? "#E4E4E4" : "#232323" },
      timeScale: { borderColor: isLight ? "#E4E4E4" : "#232323", timeVisible: true, secondsVisible: false, visible: true, ...timeScaleOptions },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: isLight ? "#B5B5B5" : "#4A4A4A", labelBackgroundColor: isLight ? "#0A0A0A" : "#F5F5F5" }, horzLine: { color: isLight ? "#B5B5B5" : "#4A4A4A", labelBackgroundColor: isLight ? "#0A0A0A" : "#F5F5F5" } },
    });
    const priceChart = createChart(priceRef.current, options(310));
    const candleSeries = priceChart.addCandlestickSeries({
      upColor, downColor, borderUpColor: upColor, borderDownColor: downColor, wickUpColor: upColor, wickDownColor: downColor,
    });
    const volumeChart = createChart(volumeRef.current, { ...options(76), timeScale: { ...options(76).timeScale, visible: false }, rightPriceScale: { ...options(76).rightPriceScale, scaleMargins: { top: 0.08, bottom: 0 } } });
    const volumeSeries = volumeChart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "", lastValueVisible: false, priceLineVisible: false });
    const rsiChart = createChart(rsiRef.current, { ...options(110), timeScale: { ...options(110).timeScale, visible: true }, rightPriceScale: { ...options(110).rightPriceScale, scaleMargins: { top: 0.12, bottom: 0.12 } } });
    const light = document.documentElement.dataset.theme === "light";
    const rsiSeries = rsiChart.addLineSeries({ color: upColor, lineWidth: 2, lastValueVisible: true, priceLineVisible: false, crosshairMarkerVisible: true });
    const rsiLevels = [30, 70].map((level) => rsiSeries.createPriceLine({
      price: level,
      color: light ? "#A8B8B1" : "#555555",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: `${level}`,
    }));
    charts.current = { price: priceChart, volume: volumeChart, rsi: rsiChart, candles: candleSeries, volumes: volumeSeries, rsiLine: rsiSeries };
    (window as any).__PRICE_CHART = priceChart;
    (window as any).__RSI_CHART = rsiChart;
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
      const chartUp = light ? "#0C9F6A" : "#22E39A";
      const chartDown = light ? "#E5354A" : "#FF4D5E";
      [priceChart, volumeChart, rsiChart].forEach((chart) => chart.applyOptions({
        layout: { textColor: light ? "#6B6B6B" : "#8A8A8A" },
        grid: { vertLines: { color: light ? "#E4E4E4" : "#232323" }, horzLines: { color: light ? "#E4E4E4" : "#232323" } },
        rightPriceScale: { borderColor: light ? "#E4E4E4" : "#232323" },
        timeScale: { borderColor: light ? "#E4E4E4" : "#232323" },
      }));
      candleSeries.applyOptions({ upColor: chartUp, downColor: chartDown, borderUpColor: chartUp, borderDownColor: chartDown, wickUpColor: chartUp, wickDownColor: chartDown });
      rsiSeries.applyOptions({ color: chartUp });
      rsiLevels.forEach((line) => line.applyOptions({ color: light ? "#A8B8B1" : "#555555" }));
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
    const nextChartDataKey = candles.length > 0
      ? `${symbol}:${interval}:${candles[0].time}:${candles[candles.length - 1].time}`
      : undefined;
    if (nextChartDataKey && chartDataKey.current !== nextChartDataKey) {
      chartDataKey.current = nextChartDataKey;
      requestAnimationFrame(() => {
        price.timeScale().fitContent();
      });
    }
  }, [candles, interval, signal?.rsi, symbol]);

  useEffect(() => {
    const candleSeries = charts.current.candles;
    const chart = charts.current.price;
    if (!candleSeries || !chart || !candles.length) {
      setMarkerTargets([]);
      setSelectedMarkers([]);
      return;
    }
    const intervalSeconds = interval === "1m" ? 60 : interval === "5m" ? 300 : interval === "15m" ? 900 : 60;

    const candlesByTime = new Map<number, Candle>(
      candles.map((candle) => [Math.floor(new Date(candle.time).getTime() / 1000), candle]),
    );
    const candleTimes = Array.from(candlesByTime.keys()).sort((a, b) => a - b);
    if (!candleTimes.length) {
      setMarkerTargets([]);
      setSelectedMarkers([]);
      return;
    }
    const minCandleTime = candleTimes[0];
    const maxCandleTime = candleTimes[candleTimes.length - 1];

    const alertsByTime = new Map<number, Alert[]>();
    for (const alert of alerts) {
      const alertTime = Math.floor(new Date(alert.time).getTime() / 1000);
      const bucketTime = Math.floor(alertTime / intervalSeconds) * intervalSeconds;

      if (bucketTime < minCandleTime || bucketTime > maxCandleTime) continue;

      let matchedTime: number | null = null;
      if (candlesByTime.has(bucketTime)) {
        matchedTime = bucketTime;
      } else {
        for (const ct of candleTimes) {
          if (Math.abs(ct - bucketTime) < intervalSeconds) {
            matchedTime = ct;
            break;
          }
        }
      }

      if (matchedTime !== null) {
        const existing = alertsByTime.get(matchedTime) ?? [];
        existing.push(alert);
        alertsByTime.set(matchedTime, existing);
      }
    }

    const updateMarkers = () => {
      const light = document.documentElement.dataset.theme === "light";
      if (!markersEnabled || alertsByTime.size === 0) {
        candleSeries.setMarkers([]);
        return;
      }
      const markers = Array.from(alertsByTime.entries())
        .sort(([a], [b]) => a - b)
        .map(([time, groupedAlerts]) => {
          const primaryAlert = groupedAlerts[0];
          const hasBuy = groupedAlerts.some((a) => a.action === "BUY");
          const hasSell = groupedAlerts.some((a) => a.action === "SELL");
          const action = hasBuy ? "BUY" : hasSell ? "SELL" : primaryAlert.action;
          const text = groupedAlerts.length > 1
            ? `${action} · ${groupedAlerts.length} signals`
            : `${primaryAlert.action} ${percent(primaryAlert.confidence)}`;
          return {
            time: time as UTCTimestamp,
            position: action === "BUY" ? ("belowBar" as const) : action === "SELL" ? ("aboveBar" as const) : ("inBar" as const),
            color: action === "BUY"
              ? (light ? "#0C9F6A" : "#22E39A")
              : action === "SELL"
                ? (light ? "#E5354A" : "#FF4D5E")
                : (light ? "#6B6B6B" : "#8A8A8A"),
            shape: action === "BUY" ? ("arrowUp" as const) : action === "SELL" ? ("arrowDown" as const) : ("circle" as const),
            text,
          };
        });
      candleSeries.setMarkers(markers);
    };

    updateMarkers();
    const themeObserver = new MutationObserver(updateMarkers);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    const updateMarkerTargets = () => {
      if (!markersEnabled || alertsByTime.size === 0) {
        setMarkerTargets([]);
        return;
      }
      const chartEl = priceRef.current;
      if (!chartEl) return;

      const timeScale = chart.timeScale();
      const chartWidth = chartEl.clientWidth || 310;
      const rightScaleWidth = (chart.priceScale("right") as any)?.width?.() ?? 55;
      const plotWidth = timeScale.width() > 0 ? timeScale.width() : (chartWidth - rightScaleWidth);
      const chartHeight = chartEl.clientHeight || 310;
      const logicalRange = timeScale.getVisibleLogicalRange();

      if (plotWidth <= 0 || !logicalRange) {
        setMarkerTargets([]);
        return;
      }

      const targets: { time: number; x: number; y: number; alerts: Alert[] }[] = [];
      for (const [time, groupedAlerts] of alertsByTime.entries()) {
        const candle = candlesByTime.get(time);
        if (!candle) continue;

        const x = timeScale.timeToCoordinate(time as UTCTimestamp);
        if (x === null) continue;

        if (x < 0 || x > plotWidth) continue;

        const primaryAlert = groupedAlerts[0];
        const hasBuy = groupedAlerts.some((a) => a.action === "BUY");
        const hasSell = groupedAlerts.some((a) => a.action === "SELL");
        const action = hasBuy ? "BUY" : hasSell ? "SELL" : primaryAlert.action;

        const markerPrice = action === "BUY" ? candle.low : action === "SELL" ? candle.high : candle.close;
        const priceY = candleSeries.priceToCoordinate(markerPrice);
        if (priceY === null) continue;

        const clampedX = Math.max(14, Math.min(plotWidth - 14, x));
        const clampedY = Math.max(14, Math.min(chartHeight - 14, priceY + (action === "BUY" ? 14 : action === "SELL" ? -14 : 0)));

        targets.push({ time, x: clampedX, y: clampedY, alerts: groupedAlerts });
      }

      setMarkerTargets(targets);
    };

    const selectAtTime = (timestamp: number | undefined) => {
      if (timestamp === undefined) return;
      const found = alertsByTime.get(timestamp);
      if (found && found.length > 0) {
        setSelectedMarkers(found);
      }
    };
    const onClick = (param: { time?: number | string | object }) =>
      selectAtTime(typeof param.time === "number" ? param.time : undefined);
    chart.subscribeClick(onClick);
    const onHover = (param: { time?: number | string | object }) =>
      selectAtTime(typeof param.time === "number" ? param.time : undefined);
    chart.subscribeCrosshairMove(onHover);

    const resizeObserver = new ResizeObserver(updateMarkerTargets);
    if (priceRef.current) resizeObserver.observe(priceRef.current);
    chart.timeScale().subscribeVisibleLogicalRangeChange(updateMarkerTargets);

    updateMarkerTargets();
    const rafId = requestAnimationFrame(() => {
      updateMarkerTargets();
    });
    const timerId = window.setTimeout(() => {
      updateMarkerTargets();
    }, 60);

    return () => {
      cancelAnimationFrame(rafId);
      window.clearTimeout(timerId);
      themeObserver.disconnect();
      chart.unsubscribeClick(onClick);
      chart.unsubscribeCrosshairMove(onHover);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(updateMarkerTargets);
      resizeObserver.disconnect();
    };
  }, [alerts, candles, interval, markersEnabled]);

  return <div className="chart-stack">
    <div className="chart-price" ref={priceRef}>
      {markersEnabled && markerTargets.map(({ time, x, y, alerts: groupedAlerts }) => <button
        key={time}
        type="button"
        className="chart-marker-hit"
        style={{ left: x, top: y }}
        aria-label={`Show ${groupedAlerts.map((alert) => `${alert.action} ${percent(alert.confidence)} ${eventName(alert.regime)} ${alert.outcome ?? "pending"}`).join("; ")}`}
        title={groupedAlerts.map((alert) => `${alert.action} · ${percent(alert.confidence)} · ${eventName(alert.regime)} · ${alert.outcome ?? "pending"}`).join("\n")}
        onMouseEnter={() => setSelectedMarkers(groupedAlerts)}
        onFocus={() => setSelectedMarkers(groupedAlerts)}
        onClick={() => setSelectedMarkers(groupedAlerts)}
      />
      )}
    </div>
    <div className="chart-subpane chart-volume-pane"><span className="chart-label">VOL</span><div ref={volumeRef} /></div>
    <div className="chart-subpane chart-rsi-pane"><span className="chart-label">RSI 14 · 30/70</span><div ref={rsiRef} /></div>
    {selectedMarkers.length > 0 && <div className="marker-details">
      {selectedMarkers.map((alert) => <div className="marker-detail-item" key={alert.id}>
        <b>{alert.action} · {percent(alert.confidence)}</b>
        <span>{eventName(alert.regime)}</span>
        <SignalOutcome alert={alert} />
      </div>)}
      <button className="text-button" onClick={() => setSelectedMarkers([])}>Close</button>
    </div>}
  </div>;
}

export function SignalCard({ signal, loading, interval = "5m" }: { signal?: Signal; loading: boolean; interval?: string }) {
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
    {signal.symbol && (
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid rgba(128,128,128,0.18)" }}>
        <SignalBreakdown symbol={signal.symbol} interval={interval} compact />
      </div>
    )}
    <div className="signal-note"><Shield size={14} /> Signals are filtered by market regime and timeframe alignment.</div>
  </Panel>;
}

export function WatchlistTable({ signals, loading, onSelect, active }: { signals: Signal[]; loading: boolean; onSelect: (symbol: string) => void; active: string }) {
  if (loading && !signals.length) return <LoadingRows count={3} />;
  return <div className="table-scroll"><table className="data-table watchlist-table"><thead><tr><th>ASSET</th><th>PRICE</th><th>1H CHANGE</th><th>RSI</th><th>VOLUME Z</th><th>SIGNAL</th></tr></thead><tbody>{signals.map((signal) => <tr key={signal.symbol} className={active === signal.symbol ? "row-active" : ""} onClick={() => onSelect(signal.symbol)}><td><div className="table-coin"><span className={`tiny-coin coin-${coinName(signal.symbol).toLowerCase()}`}>{coinName(signal.symbol)}</span><b>{coinName(signal.symbol)}</b><small>USDT</small></div></td><td className="mono">{money(signal.price)}</td><td className={`mono ${signal.change_1h >= 0 ? "positive" : "negative"}`}>{pct(signal.change_1h)}</td><td><span className={`rsi-chip ${signal.rsi > 70 ? "rsi-hot" : signal.rsi < 30 ? "rsi-cool" : ""}`}>{signal.rsi.toFixed(0)}</span></td><td className="mono">{signal.volume_z.toFixed(2)}σ</td><td><span className={`table-action action-${signal.signal.toLowerCase()}`}>{signal.signal}</span></td></tr>)}</tbody></table>{signals.length === 0 && <EmptyState title="No watchlist assets" copy="Add coins in Settings to keep an eye on them." />}</div>;
}

export function MiniAlert({ alert }: { alert: Alert }) {
  return <div className="mini-alert"><div className="mini-alert-marker"><span className={`marker-${alert.action.toLowerCase()}`} /></div><div className="mini-alert-body"><div><b>{coinName(alert.symbol)}</b><span className={`table-action action-${alert.action.toLowerCase()}`}>{alert.action}</span></div><p>{eventName(alert.event_type)} <span>·</span> {timeLabel(alert.time)}</p></div><strong className="mini-alert-confidence">{percent(alert.confidence)}</strong></div>;
}
