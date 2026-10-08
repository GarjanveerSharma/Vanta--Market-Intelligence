import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  applyTheme,
  defaultViewerPreferences,
  readViewerPreferences,
  saveViewerPreferences,
} from "../api/viewerPreferences";
import type { ViewerPreferences } from "../api/types";

interface ViewerPreferencesContextValue {
  preferences: ViewerPreferences;
  updatePreferences: (patch: Partial<ViewerPreferences>) => void;
}

const ViewerPreferencesContext = createContext<ViewerPreferencesContextValue | null>(null);

export function ViewerPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(readViewerPreferences);
  useEffect(() => {
    saveViewerPreferences(preferences);
  }, [preferences]);
  useEffect(() => {
    applyTheme(preferences.theme);
    if (preferences.theme !== "system") return;
    const media = matchMedia("(prefers-color-scheme: light)");
    const update = () => applyTheme("system");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [preferences.theme]);

  const value = useMemo(() => ({
    preferences,
    updatePreferences: (patch: Partial<ViewerPreferences>) => {
      setPreferences((current) => ({ ...current, ...patch }));
    },
  }), [preferences]);
  return <ViewerPreferencesContext.Provider value={value}>{children}</ViewerPreferencesContext.Provider>;
}

export function useViewerPreferences(): ViewerPreferencesContextValue {
  const context = useContext(ViewerPreferencesContext);
  if (!context) throw new Error("ViewerPreferencesProvider is missing");
  return context;
}

export { defaultViewerPreferences };
