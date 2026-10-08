import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, Check, Bell, Shield, Volume2, VolumeX } from "lucide-react";
import { api } from "../api/client";
import { useSignals, useApiQuery, EmptyState, ErrorNotice, PageTitle, Panel } from "../components/Shared";
import { useViewerPreferences } from "../components/ViewerPreferences";
import { coinName, percent } from "../components/format";
import type { ViewerPreferences } from "../api/types";

export default function SettingsPage() {
  const { preferences, updatePreferences } = useViewerPreferences();
  const signalsQuery = useSignals();
  const settingsQuery = useApiQuery(["calibration-settings"], api.calibrationSettings);
  const queryClient = useQueryClient();
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const [adminKey, setAdminKey] = useState("");
  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.updateCalibrationEnabled(enabled, adminKey),
    onSuccess: (settings) => {
      queryClient.setQueryData(["calibration-settings"], settings);
      setAdminKey("");
    },
  });
  const symbols = Array.from(new Set([
    ...(signalsQuery.data ?? []).map((signal) => signal.symbol),
    ...preferences.watchlist,
    preferences.default_coin,
  ]));
  const toggleWatchlist = (symbol: string) => {
    const next = preferences.watchlist.includes(symbol)
      ? preferences.watchlist.filter((item) => item !== symbol)
      : [...preferences.watchlist, symbol];
    updatePreferences({ watchlist: next });
  };

  const enableNotifications = async () => {
    if (typeof Notification === "undefined") {
      setPermission("unsupported");
      return;
    }
    const next = Notification.permission === "default"
      ? await Notification.requestPermission()
      : Notification.permission;
    setPermission(next);
    updatePreferences({ notifications_enabled: next === "granted" });
  };
  const setPreference = <K extends keyof ViewerPreferences>(key: K, value: ViewerPreferences[K]) =>
    updatePreferences({ [key]: value } as Pick<ViewerPreferences, K>);

  return <div className="page-stack">
    <PageTitle eyebrow="YOUR TERMINAL" title="Settings" subtitle="Viewer preferences are saved only in this browser." />
    <div className="settings-layout"><div className="settings-main">
      <Panel title="Market watchlist" subtitle="Select assets to show in the market overview" className="settings-panel">
        {symbols.length ? <div className="coin-picker">{symbols.map((symbol) => <button key={symbol} className={`coin-option ${preferences.watchlist.includes(symbol) ? "checked" : ""}`} onClick={() => toggleWatchlist(symbol)} aria-pressed={preferences.watchlist.includes(symbol)}>
          <span className={`tiny-coin coin-${coinName(symbol).toLowerCase()}`}>{coinName(symbol).slice(0, 1)}</span>
          <span><b>{coinName(symbol)}</b><small>{symbol}</small></span>
          <i>{preferences.watchlist.includes(symbol) && <Check size={16} />}</i>
        </button>)}</div> : <EmptyState title="No assets available yet" copy="The watchlist will populate when live symbols are configured." />}
      </Panel>
      <Panel title="Default market view" subtitle="Choose the initial chart and candle interval" className="settings-panel">
        <div className="viewer-defaults">
          <label>Default coin<select value={preferences.default_coin} onChange={(event) => setPreference("default_coin", event.target.value)}>{symbols.map((symbol) => <option key={symbol} value={symbol}>{coinName(symbol)} / USDT</option>)}</select></label>
          <label>Default interval<select value={preferences.default_interval} onChange={(event) => setPreference("default_interval", event.target.value as ViewerPreferences["default_interval"])}>{(["1m", "5m", "15m"] as const).map((interval) => <option key={interval}>{interval}</option>)}</select></label>
        </div>
      </Panel>
      <Panel title="Appearance" subtitle="System follows your device appearance preference" className="settings-panel">
        <label className="theme-select">Theme<select value={preferences.theme} onChange={(event) => setPreference("theme", event.target.value as ViewerPreferences["theme"])}><option value="system">System</option><option value="dark">Dark</option><option value="light">Light</option></select></label>
      </Panel>
      <Panel title="Browser alerts" subtitle="Notifications are sent only while this tab is open" className="settings-panel">
        <div className="notification-setting">
          <div className="notification-copy"><Bell size={17} /><div><b>Enable alerts</b><small>{permission === "granted" && preferences.notifications_enabled ? "Enabled" : permission === "denied" ? "Blocked — allow notifications in your browser site settings." : permission === "unsupported" ? "Not supported by this browser; in-app toasts are used." : "Allow desktop notifications for qualifying alerts."}</small></div></div>
          <button className="button button-subtle" onClick={enableNotifications} disabled={permission === "unsupported" || (permission === "granted" && preferences.notifications_enabled)}>
            {permission === "granted" && preferences.notifications_enabled ? "Enabled" : permission === "denied" ? "Blocked" : permission === "unsupported" ? "Not supported" : "Enable alerts"}
          </button>
        </div>
        <label className="confidence-filter setting-confidence"><span>MINIMUM CONFIDENCE <b>{percent(preferences.minimum_confidence)}</b></span><input type="range" min="0" max="0.95" step="0.05" value={preferences.minimum_confidence} onChange={(event) => setPreference("minimum_confidence", Number(event.target.value))} /></label>
        <div className="notification-setting sound-setting"><div className="notification-copy">{preferences.sound_muted ? <VolumeX size={17} /> : <Volume2 size={17} />}<div><b>Alert sound</b><small>Subtle tone when a qualifying alert arrives</small></div></div><button className={`toggle ${!preferences.sound_muted ? "on" : ""}`} role="switch" aria-checked={!preferences.sound_muted} onClick={() => setPreference("sound_muted", !preferences.sound_muted)}><i /></button></div>
      </Panel>
      <Panel title="Detection configuration" subtitle="Read-only values used by the live detector" className="settings-panel">
        {settingsQuery.isError && <ErrorNotice message={settingsQuery.error.message} />}
        {settingsQuery.data && <div className="readonly-settings">
          <span>Outcome move threshold <b>{settingsQuery.data.outcome_move_threshold_pct}%</b></span>
          <span>Alert confidence threshold <b>{settingsQuery.data.alert_confidence_threshold}</b></span>
          <span>Regime ADX threshold <b>{settingsQuery.data.regime_adx_threshold}</b></span>
          <span>High-volatility ATR threshold <b>{settingsQuery.data.regime_high_volatility_atr_pct}%</b></span>
          <span>Calibration minimum sample count <b>{settingsQuery.data.min_samples}</b></span>
          <span>Calibration low hit-rate trigger <b>{settingsQuery.data.low_hit_rate_pct}%</b></span>
          <span>Confidence adjustment step <b>{settingsQuery.data.confidence_step}</b></span>
          <span>Safe confidence range <b>{settingsQuery.data.confidence_min}–{settingsQuery.data.confidence_max}</b></span>
        </div>}
        <div className="admin-controls">
          <label>Admin API key<input autoComplete="off" type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} placeholder="Required to change calibration state" /></label>
          {settingsQuery.data && <button className="button button-subtle" onClick={() => mutation.mutate(!settingsQuery.data.enabled)} disabled={!adminKey || mutation.isPending}>
            {mutation.isPending ? "Saving…" : settingsQuery.data.enabled ? "Disable self-calibration" : "Enable self-calibration"}
          </button>}
          {mutation.isError && <p className="save-error">{mutation.error.message}</p>}
          {mutation.isSuccess && <p className="save-success"><Check size={14} />Calibration state updated.</p>}
          <small>The key is sent only in the X-Admin-Key request header and is not saved in this browser.</small>
        </div>
      </Panel>
    </div>
    <aside className="settings-aside"><div className="settings-callout"><span className="callout-spark"><Shield size={16} /></span><b>Private by default.</b><p>Watchlist, chart defaults, theme, and browser-notification preferences stay in this browser.</p><div><Activity size={14} />No account required</div></div></aside>
    </div>
  </div>;
}
