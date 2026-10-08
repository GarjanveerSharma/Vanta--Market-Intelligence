import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";
import { RealtimeBridge } from "./api/realtime";
import { ViewerPreferencesProvider } from "./components/ViewerPreferences";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000, refetchOnWindowFocus: false, refetchOnReconnect: true } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ViewerPreferencesProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <RealtimeBridge />
          <App />
        </BrowserRouter>
      </ViewerPreferencesProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
