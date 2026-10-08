import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bell, X } from "lucide-react";
import type { Alert } from "../api/types";
import { useViewerPreferences } from "./ViewerPreferences";
import { coinName, percent } from "./format";

interface Toast {
  id: number;
  alertIds: number[];
  title: string;
  body: string;
}

const SEEN_KEY = "vanta.notified-alerts";

function readSeenAlerts(): Set<string> {
  try {
    const values = JSON.parse(localStorage.getItem(SEEN_KEY) ?? "[]") as unknown;
    return new Set(Array.isArray(values) ? values.filter((value): value is string => typeof value === "string") : []);
  } catch {
    return new Set();
  }
}

function playTone(): void {
  if (!("AudioContext" in window)) return;
  try {
    const audio = new AudioContext();
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = 660;
    gain.gain.setValueAtTime(0.035, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.12);
    oscillator.connect(gain);
    gain.connect(audio.destination);
    oscillator.start();
    oscillator.stop(audio.currentTime + 0.12);
    oscillator.onended = () => void audio.close();
  } catch (error) {
    console.warn("Vanta could not play the alert tone", error);
  }
}

export function Notifications({ onUnread }: { onUnread: (count: number) => void }) {
  const { preferences } = useViewerPreferences();
  const location = useLocation();
  const navigate = useNavigate();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seen = useRef(readSeenAlerts());
  const batch = useRef<Alert[]>([]);
  const batchTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const processBatch = () => {
      batchTimer.current = undefined;
      const eligible = batch.current.splice(0).filter((alert) =>
        alert.confidence >= preferences.minimum_confidence);
      if (!eligible.length) return;
      const toast: Toast = eligible.length > 3
        ? {
          id: Date.now(),
          alertIds: eligible.map((alert) => alert.id),
          title: `${eligible.length} new Vanta signals`,
          body: eligible.map((alert) => `${coinName(alert.symbol)} ${alert.action}`).join(" · "),
        }
        : {
          id: eligible[0].id,
          alertIds: eligible.map((alert) => alert.id),
          title: eligible.length === 1 ? `${eligible[0].action} · ${coinName(eligible[0].symbol)}` : `${eligible.length} new Vanta signals`,
          body: eligible.map((alert) => `${alert.event_type} · ${percent(alert.confidence)}`).join(" · "),
        };
      setToasts((current) => [...current, toast].slice(-4));
      if (location.pathname !== "/alerts") onUnread(eligible.length);
      if (preferences.notifications_enabled && typeof Notification !== "undefined" && Notification.permission === "granted") {
        const notificationItems = eligible.length > 3 ? [null] : eligible;
        notificationItems.forEach((alert) => {
          const alertId = alert?.id ?? toast.alertIds[0];
          const notification = new Notification(
            alert ? `${alert.action} · ${coinName(alert.symbol)}` : toast.title,
            {
              body: alert ? `${alert.event_type} · ${percent(alert.confidence)}` : toast.body,
              tag: `vanta-alert-${alertId}`,
              icon: "/favicon-64.png",
            },
          );
          notification.onclick = () => {
            window.focus();
            navigate(`/alerts?alert=${alertId}`);
            notification.close();
          };
        });
      }
      if (!preferences.sound_muted) playTone();
      window.setTimeout(() => setToasts((current) => current.filter((item) => item.id !== toast.id)), 8000);
    };
    const onNewAlerts = (event: Event) => {
      const incoming = (event as CustomEvent<Alert[]>).detail;
      const unseen: Alert[] = [];
      incoming.forEach((alert) => {
        const key = `${alert.id}:${alert.time}`;
        if (!seen.current.has(key)) {
          seen.current.add(key);
          unseen.push(alert);
        }
      });
      if (!unseen.length) return;
      try {
        localStorage.setItem(SEEN_KEY, JSON.stringify(Array.from(seen.current).slice(-500)));
      } catch {
        // In-memory de-duplication still prevents repeats for this open tab.
      }
      batch.current.push(...unseen);
      if (batchTimer.current === undefined) batchTimer.current = window.setTimeout(processBatch, 450);
    };
    window.addEventListener("vanta:new-alerts", onNewAlerts);
    return () => {
      window.removeEventListener("vanta:new-alerts", onNewAlerts);
      if (batchTimer.current !== undefined) window.clearTimeout(batchTimer.current);
    };
  }, [location.pathname, navigate, onUnread, preferences.minimum_confidence, preferences.notifications_enabled, preferences.sound_muted]);

  return <div className="toast-stack" aria-live="polite">{toasts.map((toast) =>
    <button className="toast-card" key={toast.id} onClick={() => navigate(`/alerts?alert=${toast.alertIds[0]}`)}>
      <span className="toast-icon"><Bell size={16} /></span><span className="toast-copy"><b>{toast.title}</b><small>{toast.body}</small></span>
      <span className="toast-close" onClick={(event) => { event.stopPropagation(); setToasts((current) => current.filter((item) => item.id !== toast.id)); }}><X size={14} /></span>
    </button>)}</div>;
}
