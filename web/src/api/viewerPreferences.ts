import type { ViewerPreferences } from "./types";

const STORAGE_KEY = "vanta.viewer-preferences";

export const defaultViewerPreferences: ViewerPreferences = {
  watchlist: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  default_coin: "BTCUSDT",
  default_interval: "1m",
  theme: "system",
  notifications_enabled: false,
  minimum_confidence: 0.6,
  sound_muted: false,
};

export function readViewerPreferences(): ViewerPreferences {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return defaultViewerPreferences;
    const parsed = JSON.parse(stored) as Partial<ViewerPreferences>;
    return {
      ...defaultViewerPreferences,
      ...parsed,
      watchlist: Array.isArray(parsed.watchlist)
        ? parsed.watchlist.filter((coin): coin is string => typeof coin === "string")
        : defaultViewerPreferences.watchlist,
      minimum_confidence:
        typeof parsed.minimum_confidence === "number" &&
        Number.isFinite(parsed.minimum_confidence)
          ? Math.max(0, Math.min(1, parsed.minimum_confidence))
          : defaultViewerPreferences.minimum_confidence,
    };
  } catch {
    return defaultViewerPreferences;
  }
}

export function saveViewerPreferences(preferences: ViewerPreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Storage can be disabled or full; in-memory settings remain usable.
  }
}

export function applyTheme(theme: ViewerPreferences["theme"]): void {
  try {
    const resolved = theme === "system"
      ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
      : theme;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = theme;
  } catch {
    document.documentElement.dataset.theme = "dark";
    document.documentElement.dataset.themePreference = theme;
  }
}
