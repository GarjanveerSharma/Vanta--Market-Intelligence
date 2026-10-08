import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronDown, Search } from "lucide-react";
import { api } from "../api/client";
import type { Alert, Signal } from "../api/types";
import { useApiQuery, useSignals } from "../components/Shared";
import { useViewerPreferences } from "../components/ViewerPreferences";
import { coinName, money, pct } from "../components/format";
import {
  CandlestickChart,
  MiniAlert,
  SignalCard,
  TickerStrip,
  WatchlistTable,
} from "../components/MarketWidgets";
import { EmptyState, ErrorNotice, PageTitle, Panel } from "../components/Shared";

export default function LiveMarket() {
  const navigate = useNavigate();
  const { preferences, updatePreferences } = useViewerPreferences();
  const [symbol, setSymbol] = useState(preferences.default_coin);
  const [interval, setInterval] = useState(preferences.default_interval);
  const [markersEnabled, setMarkersEnabled] = useState(true);
  const [markerFilter, setMarkerFilter] = useState<Signal["signal"] | "ALL">("ALL");
  const signalsQuery = useSignals();
  const signals = signalsQuery.data ?? [];
  const selected = signals.find((signal) => signal.symbol === symbol);
  const activeSymbol = selected?.symbol ?? symbol;
  const candlesQuery = useApiQuery(
    ["candles", activeSymbol, interval],
    () => api.candles(activeSymbol, interval),
  );
  const alertsQuery = useApiQuery(
    ["alerts", activeSymbol],
    () => api.alerts(activeSymbol),
  );
  const candles = candlesQuery.data ?? [];
  const symbolOptions = Array.from(new Set([
    ...signals.map((signal) => signal.symbol),
    ...preferences.watchlist,
  ]));
  const recentAlerts = (alertsQuery.data ?? []).slice(0, 4);
  const chartMarkers = (alertsQuery.data ?? []).filter((alert) =>
    markerFilter === "ALL" || alert.action === markerFilter);
  const selectCoin = (coin: string) => {
    setSymbol(coin);
    updatePreferences({ default_coin: coin });
  };

  return <motion.div className="page-stack" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
    <PageTitle eyebrow="MARKET OVERVIEW" title="Live Market" subtitle="Real-time signals and market structure, all in one view." />
    {signalsQuery.isError && <ErrorNotice message={signalsQuery.error.message} />}
    <TickerStrip signals={signals} active={activeSymbol} onSelect={selectCoin} />
    <div className="market-layout">
      <div className="market-primary">
        <Panel className="chart-panel">
          <div className="chart-toolbar">
            <div className="asset-heading">
              <div className={`coin-icon coin-${coinName(activeSymbol).toLowerCase()}`}>{coinName(activeSymbol).slice(0, 1)}</div>
              <div>
                <div className="asset-symbol">{coinName(activeSymbol)} <span>/ USDT</span></div>
                <div className="asset-price">
                  {selected ? money(selected.price) : "—"}
                  <span className={selected && selected.change_1h < 0 ? "negative" : "positive"}>{selected ? pct(selected.change_1h) : "—"} <small>1h</small></span>
                </div>
              </div>
            </div>
            <div className="chart-controls">
              <label className="select-wrap">
                <Search size={14} />
                <select value={activeSymbol} onChange={(event) => selectCoin(event.target.value)} aria-label="Select coin">
                  {symbolOptions.map((coin) => <option key={coin} value={coin}>{coinName(coin)} / USDT</option>)}
                </select>
                <ChevronDown size={13} />
              </label>
              <div className="interval-switch">{(["1m", "5m", "15m"] as const).map((value) =>
                <button key={value} onClick={() => { setInterval(value); updatePreferences({ default_interval: value }); }} className={interval === value ? "selected" : ""}>{value}</button>)}</div>
            </div>
          </div>
          {candles.length ? (
            <CandlestickChart
              candles={candles}
              signal={selected}
              interval={interval}
              alerts={chartMarkers}
              markersEnabled={markersEnabled}
            />
          ) : candlesQuery.isError ? (
            <EmptyState title="No candle history" copy="Candles will appear after the server has market data for this coin and interval." />
          ) : (
            <div className="chart-skeleton"><div className="skeleton" /></div>
          )}
          <div className="chart-marker-controls">
            <label><input type="checkbox" checked={markersEnabled} onChange={(event) => setMarkersEnabled(event.target.checked)} /> Show signals</label>
            <label>Signal type <select value={markerFilter} onChange={(event) => setMarkerFilter(event.target.value as Signal["signal"] | "ALL")}>
              <option value="ALL">All</option>{(["BUY", "SELL", "HOLD", "AVOID"] as const).map((type) => <option key={type}>{type}</option>)}
            </select></label>
          </div>
          <div className="chart-legend"><span><i className="legend-candle" />Price</span><span><i className="legend-volume" />Volume</span><span><i className="legend-rsi" />RSI (14)</span><span className="chart-range">{candles.length} candles <span>·</span> Live updates</span></div>
        </Panel>
        <Panel title="Watchlist" subtitle="Your selected markets at a glance" className="watchlist-panel" action={<button className="text-button" onClick={() => navigate("/settings")}>Manage watchlist</button>}>
          <WatchlistTable signals={signals.filter((signal) => preferences.watchlist.includes(signal.symbol))} loading={signalsQuery.isLoading} onSelect={selectCoin} active={activeSymbol} />
        </Panel>
      </div>
      <div className="market-aside">
        <SignalCard signal={selected} loading={signalsQuery.isLoading} />
        <Panel title="Recent alerts" subtitle={`Latest signals for ${coinName(activeSymbol)}`} className="recent-alerts" action={<Link className="text-button" to="/alerts">View all</Link>}>
          {alertsQuery.isLoading ? <div className="loading-rows"><div className="skeleton" /></div> : alertsQuery.isError ? <ErrorNotice compact message={alertsQuery.error.message} /> : recentAlerts.length ? <div className="recent-list">{recentAlerts.map((alert: Alert) => <MiniAlert key={alert.id} alert={alert} />)}</div> : <EmptyState title="No recent alerts" copy="New signals for this market will show up here." />}
        </Panel>
      </div>
    </div>
  </motion.div>;
}
