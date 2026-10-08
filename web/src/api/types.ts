export type Action = "BUY" | "SELL" | "HOLD" | "AVOID";

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Signal {
  symbol: string;
  price: number;
  change_1h: number;
  rsi: number;
  volume_z: number;
  signal: Action;
  confidence: number;
  regime?: string;
  timeframe_agreement?: Record<string, boolean>;
  track_record?: Record<string, unknown>;
  filter_version?: string;
  signal_quality?: string;
  adx?: number | null;
  atr_pct?: number | null;
}

export interface Alert {
  id: number;
  time: string;
  symbol: string;
  event_type: string;
  action: Action;
  confidence: number;
  price: number;
  stop_loss: number;
  explanation: string;
  regime?: string;
  filter_version?: string;
  timeframe_agreement?: Record<string, boolean>;
  track_record?: Record<string, unknown>;
  hit_rate_pct?: number | null;
  sample_count?: number;
  outcome?: "correct" | "wrong" | "pending";
}

export interface ViewerPreferences {
  watchlist: string[];
  default_coin: string;
  default_interval: "1m" | "5m" | "15m";
  theme: "system" | "dark" | "light";
  notifications_enabled: boolean;
  minimum_confidence: number;
  sound_muted: boolean;
}

export interface TrackRecord {
  symbol: string;
  event_type: string;
  hit_rate_pct: number | null;
  sample_count: number;
  correct_count: number;
  regime: string | null;
  filter_version: string;
  enough_data: boolean;
}

export interface CalibrationChange {
  changed_at: string;
  event_type: string;
  old_threshold: number;
  new_threshold: number;
  hit_rate_pct: number;
  sample_count: number;
  reason: string;
}

export interface CalibrationSettings {
  enabled: boolean;
  outcome_move_threshold_pct: number;
  alert_confidence_threshold: number;
  regime_adx_threshold: number;
  regime_high_volatility_atr_pct: number;
  high_volatility_confidence_multiplier: number;
  high_volatility_stop_multiplier: number;
  min_samples: number;
  low_hit_rate_pct: number;
  confidence_step: number;
  confidence_min: number;
  confidence_max: number;
}

export interface Backtest {
  total_alerts: number;
  precision: number;
  recall: number;
  avg_latency_ms: number;
  pnl_pct: number;
  by_event: { event_type: string; alerts: number; true_positives: number; precision: number; avg_lead_seconds: number }[];
  equity: { time: string; equity: number }[];
}
