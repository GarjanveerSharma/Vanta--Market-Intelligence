import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bell, CircleHelp, ExternalLink, LayoutDashboard, Menu, Settings as SettingsIcon, Shield, Sparkles, TrendingUp, X } from "lucide-react";
import { api } from "./api/client";
import { useRealtimeStatus } from "./api/realtime";
import { LiveIndicator } from "./components/Shared";
import { Notifications } from "./components/Notifications";
import { useViewerPreferences } from "./components/ViewerPreferences";
import { PAGE_PATHS } from "./pages/routes";
import LiveMarket from "./pages/LiveMarket";
import AlertsPage from "./pages/Alerts";
import TrackRecordPage from "./pages/TrackRecord";
import BacktestPage from "./pages/Backtest";
import SettingsPage from "./pages/Settings";
import GuidePage from "./pages/Guide";

const NAV = [
  { to: PAGE_PATHS.liveMarket, label: "Live Market", icon: LayoutDashboard },
  { to: PAGE_PATHS.alerts, label: "Alerts", icon: Bell },
  { to: PAGE_PATHS.trackRecord, label: "Track Record", icon: Activity },
  { to: PAGE_PATHS.backtest, label: "Backtest", icon: TrendingUp },
  { to: PAGE_PATHS.settings, label: "Settings", icon: SettingsIcon },
  { to: PAGE_PATHS.guide, label: "Guide", icon: CircleHelp },
];

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [failureSince, setFailureSince] = useState<number | null>(Date.now());
  const [clock, setClock] = useState(Date.now());
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const realtime = useRealtimeStatus();
  const { preferences, updatePreferences } = useViewerPreferences();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10_000,
    retry: false,
  });
  const isLive = realtime === "connected" || (health.isSuccess && !health.isError && health.data.status === "ok");
  const [retryAge, setRetryAge] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (isLive) setFailureSince(null);
    else setFailureSince((current) => current ?? Date.now());
  }, [isLive]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (failureSince !== null) setRetryAge(Date.now() - failureSince);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [failureSince]);
  useEffect(() => {
    document.title = unread ? `(${unread}) Vanta` : "Vanta — Market Intelligence";
  }, [unread]);
  useEffect(() => {
    if (location.pathname === PAGE_PATHS.alerts) setUnread(0);
    setMenuOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    const onNavigate = (event: Event) => navigate((event as CustomEvent<string>).detail);
    window.addEventListener("vanta:navigate", onNavigate);
    return () => window.removeEventListener("vanta:navigate", onNavigate);
  }, [navigate]);
  const recordUnread = useCallback((count: number) => {
    setUnread((current) => current + count);
  }, []);
  const retry = async () => {
    setFailureSince(Date.now());
    setRetryAge(0);
    await health.refetch();
    await queryClient.invalidateQueries();
  };
  const waitingForServer = !isLive && failureSince !== null && retryAge < 90_000;

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
      <Link to="/" className="brand-lockup" aria-label="Vanta home">
        <img src="/vanta-logo-dark.svg" alt="" className="brand-logo" />
        <span className="brand-copy"><strong>VANTA</strong><small>MARKET INTELLIGENCE</small></span>
        <button className="icon-button sidebar-close" onClick={(event) => { event.preventDefault(); setMenuOpen(false); }} aria-label="Close menu"><X size={19} /></button>
      </Link>
      <LiveIndicator live={isLive} />
      <div className="nav-caption">WORKSPACE</div>
      <nav className="main-nav" aria-label="Main navigation">
        {NAV.map(({ to, label, icon: Icon }) =>
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{label === "Alerts" && unread > 0 && <span className="nav-unread">{unread > 99 ? "99+" : unread}</span>}
          </NavLink>)}
      </nav>
      <div className="sidebar-bottom">
        <label className="sidebar-theme">Theme<select value={preferences.theme} onChange={(event) => updatePreferences({ theme: event.target.value as typeof preferences.theme })}>
          <option value="system">System</option><option value="dark">Dark</option><option value="light">Light</option>
        </select></label>
        <Link className="sidebar-help" to={PAGE_PATHS.guide}><span className="help-icon"><CircleHelp size={16} /></span><div><strong>Need a hand?</strong><small>Explore the user guide</small></div><ExternalLink size={13} /></Link>
        <div className="sidebar-version"><span className="version-mark"><Sparkles size={13} /></span>Vanta Terminal <span>v1.0</span></div>
      </div>
    </aside>
    {menuOpen && <button className="mobile-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
    <div className="main-area">
      <header className="topbar">
        <button className="icon-button mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
        <div className="breadcrumb"><span>Terminal</span><span className="crumb-slash">/</span><strong>{NAV.find((item) => item.to === location.pathname)?.label ?? "Live Market"}</strong></div>
        <div className="topbar-right">
          <div className="market-clock"><span className="clock-dot" />MARKET OPEN <span className="clock-divider">·</span><span>{new Date(clock).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC</span></div>
          <button className="topbar-alert" onClick={() => navigate("/alerts")} aria-label="Open alerts"><Bell size={17} />{unread > 0 && <i />}</button>
        </div>
      </header>
      <main className="page-content">
        {!isLive && <section className={`server-status ${waitingForServer ? "is-waking" : "is-unreachable"}`} role="status">
          {waitingForServer
            ? <><span className="server-spinner" /><b>Server is waking up… (~1 min)</b><small>Waiting for the live market connection.</small></>
            : <><span className="server-error-mark">!</span><b>Can’t reach the server</b><small>Check your connection or try again.</small><button className="button button-subtle" onClick={() => void retry()}>Retry</button></>}
        </section>}
        <Routes>
          <Route path={PAGE_PATHS.liveMarket} element={<LiveMarket />} />
          <Route path={PAGE_PATHS.alerts} element={<AlertsPage />} />
          <Route path={PAGE_PATHS.trackRecord} element={<TrackRecordPage />} />
          <Route path={PAGE_PATHS.backtest} element={<BacktestPage />} />
          <Route path={PAGE_PATHS.settings} element={<SettingsPage />} />
          <Route path={PAGE_PATHS.guide} element={<GuidePage />} />
          <Route path="*" element={<LiveMarket />} />
        </Routes>
      </main>
      <footer className="app-footer"><span>© 2026 Vanta Intelligence</span><span><Shield size={13} /> Signals are automated and can be wrong. Not financial advice.</span></footer>
    </div>
    <Notifications onUnread={recordUnread} />
  </div>;
}
